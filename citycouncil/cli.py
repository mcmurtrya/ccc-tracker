from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path

import uvicorn

from citycouncil.config import get_settings
from citycouncil.csv_loader import load_csv_standalone
from citycouncil.csv_promote import promote_standalone, reconciliation_standalone
from citycouncil.ingest.documents_extract import extract_documents_standalone
from citycouncil.ingest.documents_sync import sync_documents_standalone
from citycouncil.ingest.embed_jobs import embed_run_standalone
from citycouncil.ingest.poller import run_poll_standalone
from citycouncil.pipeline import run_pipeline_standalone

ROOT = Path(__file__).resolve().parents[1]


def _ensure_config_loaded() -> None:
    """Load and validate settings so bad env fails before any subcommand runs."""
    get_settings()


def run_async(coro_factory: Callable[[], Awaitable[object]]) -> None:
    asyncio.run(coro_factory())


def _print_json(obj: object) -> None:
    print(json.dumps(obj, indent=2, default=str))


def _reject_mutually_exclusive_flags(flag_a: bool, flag_b: bool, message: str) -> None:
    if flag_a and flag_b:
        raise SystemExit(message)


def _cmd_migrate(_: argparse.Namespace) -> None:
    subprocess.check_call([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT)


def _cmd_poll(_: argparse.Namespace) -> None:
    async def _run() -> None:
        out = await run_poll_standalone()
        _print_json(out)

    run_async(_run)


def _cmd_sync_documents(args: argparse.Namespace) -> None:
    async def _run() -> None:
        out = await sync_documents_standalone(meeting_external_id=args.meeting_external_id)
        _print_json(out)

    run_async(_run)


def _cmd_extract_documents(args: argparse.Namespace) -> None:
    async def _run() -> None:
        aid = uuid.UUID(args.artifact_id) if args.artifact_id else None
        out = await extract_documents_standalone(
            limit=args.limit,
            artifact_id=aid,
            status_filter=args.status,
        )
        _print_json(out)

    run_async(_run)


def _cmd_embed_run(args: argparse.Namespace) -> None:
    _reject_mutually_exclusive_flags(
        args.enqueue_only,
        args.process_only,
        "Cannot combine --enqueue-only and --process-only",
    )

    async def _run() -> None:
        out = await embed_run_standalone(
            enqueue_only=args.enqueue_only,
            process_only=args.process_only,
            enqueue_limit=args.enqueue_limit,
            process_limit=args.process_limit,
        )
        _print_json(out)

    run_async(_run)


def _cmd_pipeline(args: argparse.Namespace) -> None:
    _reject_mutually_exclusive_flags(
        args.embed_enqueue_only,
        args.embed_process_only,
        "Cannot combine --embed-enqueue-only and --embed-process-only",
    )

    async def _run() -> None:
        out = await run_pipeline_standalone(
            run_migrate=not args.skip_migrate,
            run_poll=not args.skip_poll,
            run_sync_documents=not args.skip_sync_documents,
            run_extract_documents=not args.skip_extract_documents,
            run_embed_run=not args.skip_embed_run,
            meeting_external_id=args.meeting_external_id,
            extract_limit=args.extract_limit,
            extract_status=args.extract_status,
            embed_enqueue_only=args.embed_enqueue_only,
            embed_process_only=args.embed_process_only,
            embed_enqueue_limit=args.embed_enqueue_limit,
            embed_process_limit=args.embed_process_limit,
        )
        _print_json(out)

    run_async(_run)


def _cmd_load_csv(args: argparse.Namespace) -> None:
    async def _run() -> None:
        out = await load_csv_standalone(args.path)
        _print_json(
            {
                "batch_id": out.batch_id,
                "file_sha256": out.file_sha256,
                "row_count": out.row_count,
                "accepted_count": out.accepted_count,
                "duplicate_file_count": out.duplicate_file_count,
                "duplicate_db_count": out.duplicate_db_count,
                "invalid_count": out.invalid_count,
            }
        )

    run_async(_run)


def _cmd_promote_csv(args: argparse.Namespace) -> None:
    async def _run() -> None:
        bid = uuid.UUID(args.batch_id) if args.batch_id else None
        out = await promote_standalone(batch_id=bid)
        _print_json({"promoted": out.promoted, "failed": out.failed})

    run_async(_run)


def _cmd_csv_reconcile(args: argparse.Namespace) -> None:
    async def _run() -> None:
        bid = uuid.UUID(args.batch_id) if args.batch_id else None
        out = await reconciliation_standalone(batch_id=bid)
        _print_json(out)

    run_async(_run)


def _cmd_serve(args: argparse.Namespace) -> None:
    uvicorn.run(
        "citycouncil.api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="citycouncil")
    sub = parser.add_subparsers(dest="command", required=True)

    p_migrate = sub.add_parser("migrate", help="Run Alembic migrations (upgrade head)")
    p_migrate.set_defaults(func=_cmd_migrate)

    p_poll = sub.add_parser(
        "poll",
        help="Run one ingestion cycle (fixture: CITYCOUNCIL_POLLER_USE_FIXTURE=1; "
        "live enrich: CITYCOUNCIL_ELMS_ENRICH_DETAIL=1 — see .env.example)",
    )
    p_poll.set_defaults(func=_cmd_poll)

    p_docs = sub.add_parser(
        "sync-documents",
        help="Download ELMS meeting files (PDFs by default) into document_artifacts (see docs/TICKETS.md DOC-003)",
    )
    p_docs.add_argument(
        "--meeting-external-id",
        type=str,
        default=None,
        metavar="UUID",
        help="Only sync files for this meeting external_id (ELMS meetingId)",
    )
    p_docs.set_defaults(func=_cmd_sync_documents)

    p_ex = sub.add_parser(
        "extract-documents",
        help="TXT-101/102: PyMuPDF → document_chunks; sets parse_status ok/failed",
    )
    p_ex.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max pending artifacts (default: CITYCOUNCIL_EXTRACT_MAX_DOCUMENTS)",
    )
    p_ex.add_argument(
        "--artifact-id",
        type=str,
        default=None,
        metavar="UUID",
        help="Extract only this document_artifacts.id (ignores --limit and --status)",
    )
    p_ex.add_argument(
        "--status",
        choices=["pending", "failed", "pending_or_failed", "all"],
        default="pending",
        help="Which parse_status rows to process (default: pending only)",
    )
    p_ex.set_defaults(func=_cmd_extract_documents)

    p_emb = sub.add_parser(
        "embed-run",
        help="LLM-203: enqueue embed_chunk jobs for chunks without embedding, then Hugging Face feature-extraction",
    )
    p_emb.add_argument(
        "--enqueue-only",
        action="store_true",
        help="Only create llm_jobs rows (no embedding API call)",
    )
    p_emb.add_argument(
        "--process-only",
        action="store_true",
        help="Only process pending embed_chunk jobs (requires CITYCOUNCIL_HUGGINGFACE_TOKEN)",
    )
    p_emb.add_argument(
        "--enqueue-limit",
        type=int,
        default=None,
        metavar="N",
        help="Override CITYCOUNCIL_EMBED_ENQUEUE_LIMIT for this run",
    )
    p_emb.add_argument(
        "--process-limit",
        type=int,
        default=None,
        metavar="N",
        help="Override CITYCOUNCIL_EMBED_PROCESS_LIMIT for this run",
    )
    p_emb.set_defaults(func=_cmd_embed_run)

    p_pipe = sub.add_parser(
        "pipeline",
        help="Run migrate → poll → sync-documents → extract-documents → embed-run (use --skip-* to omit steps)",
    )
    p_pipe.add_argument(
        "--skip-migrate",
        action="store_true",
        help="Do not run alembic upgrade head",
    )
    p_pipe.add_argument("--skip-poll", action="store_true", help="Skip poll step")
    p_pipe.add_argument(
        "--skip-sync-documents",
        action="store_true",
        help="Skip sync-documents step",
    )
    p_pipe.add_argument(
        "--skip-extract-documents",
        action="store_true",
        help="Skip extract-documents step",
    )
    p_pipe.add_argument("--skip-embed-run", action="store_true", help="Skip embed-run step")
    p_pipe.add_argument(
        "--meeting-external-id",
        type=str,
        default=None,
        metavar="UUID",
        help="Passed to sync-documents: only sync files for this meeting external_id",
    )
    p_pipe.add_argument(
        "--extract-limit",
        type=int,
        default=None,
        metavar="N",
        help="Max artifacts for extract-documents (default: CITYCOUNCIL_EXTRACT_MAX_DOCUMENTS)",
    )
    p_pipe.add_argument(
        "--extract-status",
        choices=["pending", "failed", "pending_or_failed", "all"],
        default="pending",
        help="parse_status filter for extract-documents (default: pending)",
    )
    p_pipe.add_argument(
        "--embed-enqueue-only",
        action="store_true",
        help="embed-run: only enqueue llm_jobs",
    )
    p_pipe.add_argument(
        "--embed-process-only",
        action="store_true",
        help="embed-run: only process pending embed jobs",
    )
    p_pipe.add_argument(
        "--embed-enqueue-limit",
        type=int,
        default=None,
        metavar="N",
        help="Override CITYCOUNCIL_EMBED_ENQUEUE_LIMIT for embed-run",
    )
    p_pipe.add_argument(
        "--embed-process-limit",
        type=int,
        default=None,
        metavar="N",
        help="Override CITYCOUNCIL_EMBED_PROCESS_LIMIT for embed-run",
    )
    p_pipe.set_defaults(func=_cmd_pipeline)

    p_csv = sub.add_parser("load-csv", help="P2-301: validate CSV, dedupe, bulk insert to staging")
    p_csv.add_argument("path", type=Path, help="Path to CSV file")
    p_csv.set_defaults(func=_cmd_load_csv)

    p_prom = sub.add_parser(
        "promote-csv",
        help="Promote accepted staging rows into meetings + ordinances",
    )
    p_prom.add_argument(
        "--batch-id",
        type=str,
        default=None,
        help="Limit to one import batch UUID (default: all pending batches)",
    )
    p_prom.set_defaults(func=_cmd_promote_csv)

    p_rec = sub.add_parser("csv-reconcile", help="P2-302: staging/core counts and orphan check")
    p_rec.add_argument("--batch-id", type=str, default=None, help="Filter to one batch UUID")
    p_rec.set_defaults(func=_cmd_csv_reconcile)

    p_serve = sub.add_parser("serve", help="Start FastAPI (uvicorn)")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.add_argument("--reload", action="store_true")
    p_serve.set_defaults(func=_cmd_serve)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    _ensure_config_loaded()
    args.func(args)


if __name__ == "__main__":
    main()
