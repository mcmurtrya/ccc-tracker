# citycouncil

Chicago City Council legislative data ingestion and API.

## Overview

This project **pulls** legislative data (eLMS-style polls, optional CSV backfills, meeting PDFs), **normalizes** it into Postgres (with **pgvector** for embeddings), and **serves** a FastAPI app:

- **Public:** meetings list/detail, ordinances, merged activity feed, RSS, semantic search over document chunks (RAG).
- **Admin (API key):** exports, document stats, DLQ, alert subscriptions, ordinance summarization, HTTP-triggered poll.
- **CLI:** migrations, ingestion pipeline (poll → sync PDFs → extract text → embed), CSV staging/promote/reconcile, `uvicorn` server.

Run `uv run citycouncil --help` for all subcommands.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (install: `curl -LsSf https://astral.sh/uv/install.sh | sh` or your package manager)
- Python 3.12+ (uv will download a matching interpreter if needed)

## Setup

```bash
uv sync
```

This creates `.venv`, installs runtime + **dev** dependencies (see `[dependency-groups]` and `tool.uv.default-groups` in `pyproject.toml`), and uses **`uv.lock`** for reproducible installs.

- Add a dependency: edit `pyproject.toml`, then `uv lock` and commit `uv.lock`.
- Production / CI without dev tools: `uv sync --no-dev`

## Useful commands

Run everything via **`uv run`** (uses the project `.venv`) from the **repository root** (the directory that contains `pyproject.toml` and `tests/`).

### Environment and dependencies

| Command | Purpose |
|--------|---------|
| `cp .env.example .env` | Create local env file; edit `CITYCOUNCIL_*` values. |
| `uv sync` | Install deps from `uv.lock` (includes dev group by default). |
| `uv lock` | Regenerate `uv.lock` after changing `pyproject.toml`. |
| `uv sync --no-dev` | Production-style install (no dev/test tools). |

### Database

| Command | Purpose |
|--------|---------|
| `docker compose up -d` | Start Postgres (**pgvector** image) on **localhost:5433** (see `docker-compose.yml`; avoids conflict with a system Postgres on 5432). |
| `uv run citycouncil migrate` | Apply Alembic migrations (`upgrade head`). |
| `uv run python -m alembic current` | Show current migration revision. |
| `uv run python -m alembic history` | List migration history. |

### API server

| Command | Purpose |
|--------|---------|
| `uv run citycouncil serve` | Start API on `http://127.0.0.1:8000`. |
| `uv run citycouncil serve --port 8001` | Use another port if 8000 is busy. |
| `uv run citycouncil serve --host 0.0.0.0` | Listen on all interfaces (e.g. LAN). |
| `uv run citycouncil serve --reload` | Auto-reload on code changes (dev). |

### CLI ingestion (no HTTP)

| Command | Purpose |
|--------|---------|
| `uv run citycouncil poll` | One eLMS poll cycle (`CITYCOUNCIL_POLLER_USE_FIXTURE=1` = offline fixture). Live API: set `CITYCOUNCIL_ELMS_ENRICH_DETAIL=1` to load agenda, matters, and roll-call votes (see `.env.example`; caps apply). |
| `uv run citycouncil load-csv fixtures/sample_backfill.csv` | Validate CSV → staging tables. |
| `uv run citycouncil promote-csv` | Promote accepted staging rows → `meetings` / `ordinances`. |
| `uv run citycouncil promote-csv --batch-id '<uuid>'` | Promote one import batch only. |
| `uv run citycouncil csv-reconcile` | Staging vs core counts / orphan check (P2-302). |
| `uv run citycouncil csv-reconcile --batch-id '<uuid>'` | Reconcile one batch. |
| `uv run citycouncil sync-documents` | Download ELMS meeting PDFs into `document_artifacts` (needs `files` on meeting `raw_json`; see `docs/TICKETS.md`). |
| `uv run citycouncil sync-documents --meeting-external-id '<uuid>'` | Sync PDFs for one meeting only. |
| `uv run citycouncil extract-documents` | PyMuPDF → `document_chunks`; pending `document_artifacts` only (see `docs/TICKETS.md` TXT-101/102). |
| `uv run citycouncil extract-documents --artifact-id '<uuid>'` | Extract one artifact by id. |
| `uv run citycouncil extract-documents --status failed` | Retry failed artifacts only. |
| `uv run citycouncil extract-documents --status all` | Re-extract including `ok` (replace chunks). |
| `uv run citycouncil embed-run` | Enqueue `embed_chunk` jobs for chunks without `embedding`, then call [Hugging Face Inference](https://huggingface.co/docs/api-inference/quicktour) feature-extraction (needs `CITYCOUNCIL_HUGGINGFACE_TOKEN` with Inference Providers access; default model `sentence-transformers/all-MiniLM-L6-v2`, 384-dim — align `CITYCOUNCIL_EMBEDDING_DIMENSIONS` with your model). |
| `uv run citycouncil embed-run --enqueue-only` | Create `llm_jobs` only (no API key needed). |
| `uv run citycouncil embed-run --process-only` | Process pending embedding jobs only. |
| `uv run citycouncil pipeline` | **Ordered run:** migrate → poll → sync-documents → extract-documents → embed-run. Use `--skip-migrate`, `--skip-poll`, `--skip-sync-documents`, `--skip-extract-documents`, `--skip-embed-run` to omit steps; pass `--extract-limit`, `--embed-process-limit`, etc. as needed. |

### Tests

| Command | Purpose |
|--------|---------|
| `uv run pytest` | Unit tests under `tests/` (fast; no Docker required). Coverage runs by default (`pytest-cov` in `pyproject.toml`; threshold **64%**). |
| `uv run pytest tests/` | Same as above; use this form if your **current directory is not the repo root** (see note below). |
| `uv run pytest tests/integration -m integration` | Integration tests (Postgres + Docker **or** set `CITYCOUNCIL_INTEGRATION_DATABASE_URL`). |

**Note:** Pytest only applies configured `testpaths` when you start it with **no path arguments** and your **shell cwd is the repo root**. If you run plain `pytest` from a subdirectory (e.g. inside the `citycouncil/` package folder), it may collect **zero** tests. Fix: `cd` to the repo root, or pass an explicit path such as `uv run pytest tests/` or `uv run pytest ../tests` relative to where you are.

### HTTP examples (with server running)

Replace host/port if you used `--port`. Set `CITYCOUNCIL_ADMIN_API_KEY` in `.env` for `/admin/*`.

| Command | Purpose |
|--------|---------|
| `curl -s http://127.0.0.1:8000/health` | Liveness. |
| `curl -s http://127.0.0.1:8000/meetings` | List meetings (requires DB + data). |
| `curl -s http://127.0.0.1:8000/meetings/<uuid>` | Meeting detail: agenda, votes + roll call, document metadata (public). |
| `curl -s "http://127.0.0.1:8000/activity?since=2026-01-01T00:00:00Z"` | Activity feed: meetings + ordinances (by `updated_at`) and documents (by `created_at`), merged newest-first. Omit `since` for default window (`CITYCOUNCIL_ACTIVITY_DEFAULT_SINCE_DAYS`). Use `types=`, `limit`, `offset`, optional `q=` substring filter. |
| `curl -s "http://127.0.0.1:8000/feed.xml"` | RSS 2.0 for the same activity stream (readers / reporters). Tune with `since`, `types`, `q`, `limit` (max 100). Set `CITYCOUNCIL_PUBLIC_BASE_URL` for permalinks. |
| `curl -s "http://127.0.0.1:8000/ordinances/<uuid>"` | Public ordinance title, tags, optional LLM fields. |
| `curl -s "http://127.0.0.1:8000/alerts/unsubscribe?token=<token>"` | Deactivate email alert subscription (token from `POST /admin/subscriptions`). |
| `curl -s -X POST -H "Content-Type: application/json" -H "X-Admin-Key: $CITYCOUNCIL_ADMIN_API_KEY" -d '{"email":"you@example.com","types":"meetings,ordinances","q":"zoning"}' http://127.0.0.1:8000/admin/subscriptions` | Create alert subscription row (email delivery requires your own SMTP/cron). |
| `curl -H "X-Admin-Key: $CITYCOUNCIL_ADMIN_API_KEY" http://127.0.0.1:8000/admin/dlq` | List ingest dead-letter rows. |
| `curl -s -H "X-Admin-Key: $CITYCOUNCIL_ADMIN_API_KEY" http://127.0.0.1:8000/admin/documents/stats` | Document + chunk counts, embeddings, `llm_jobs` pending (DOC-005 / LLM-201/203). |
| `curl -s -H "X-Admin-Key: $CITYCOUNCIL_ADMIN_API_KEY" -o meetings.csv "http://127.0.0.1:8000/admin/export/meetings?fmt=csv"` | Bulk CSV export of meetings (also `/admin/export/ordinances`, `/votes`, `/vote-members`; `fmt=json` for JSON). |
| `curl -s "http://127.0.0.1:8000/search/chunks?q=zoning&limit=5"` | RAG: semantic search (needs HF token + pgvector + `embed-run`). Each hit includes `body_preview`, `meeting`, `document` metadata; response adds `citations` (chunk ids + scores), `embedding_model`, and `disclaimer` (Phase 6 trust layer). |
| `curl -s -X POST -H "X-Admin-Key: $CITYCOUNCIL_ADMIN_API_KEY" http://127.0.0.1:8000/admin/ordinances/<uuid>/summarize` | LLM-202: fill `llm_summary` / `llm_tags` via HF chat. |
| `curl -X POST -H "X-Admin-Key: $CITYCOUNCIL_ADMIN_API_KEY" http://127.0.0.1:8000/admin/poll` | Trigger one poll via HTTP. |

Generate an admin key (store in `.env` as `CITYCOUNCIL_ADMIN_API_KEY`):

```bash
openssl rand -hex 32
```

Admin routes return **503** if `CITYCOUNCIL_ADMIN_API_KEY` is unset.

## Docker image build

The multi-stage template under `infra/.../docker-templates/Dockerfile.python.multistage` expects `pyproject.toml`, `uv.lock`, and the `citycouncil/` package in the build context.

Do not use `pip` in this repo for local development; use **`uv sync`** / **`uv run`**.
