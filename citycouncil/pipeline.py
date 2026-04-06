"""Ordered ingestion pipeline: migrate → poll → sync-documents → extract-documents → embed-run."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from citycouncil.config import Settings, get_settings
from citycouncil.ingest.documents_extract import extract_documents_standalone
from citycouncil.ingest.documents_sync import sync_documents_standalone
from citycouncil.ingest.embed_jobs import embed_run_standalone
from citycouncil.ingest.poller import run_poll_standalone

ROOT = Path(__file__).resolve().parents[1]


async def run_pipeline_standalone(
    settings: Settings | None = None,
    *,
    run_migrate: bool = True,
    run_poll: bool = True,
    run_sync_documents: bool = True,
    run_extract_documents: bool = True,
    run_embed_run: bool = True,
    meeting_external_id: str | None = None,
    extract_limit: int | None = None,
    extract_status: str = "pending",
    embed_enqueue_only: bool = False,
    embed_process_only: bool = False,
    embed_enqueue_limit: int | None = None,
    embed_process_limit: int | None = None,
) -> dict[str, Any]:
    """Run CLI ingestion steps in a fixed order (see module docstring).

    Each step uses the same standalone helpers as the individual ``citycouncil`` subcommands.
    """
    if embed_enqueue_only and embed_process_only:
        raise ValueError("Cannot combine enqueue-only and process-only")
    settings = settings or get_settings()
    out: dict[str, Any] = {"steps": []}

    def _append(name: str, result: Any) -> None:
        out["steps"].append({"step": name, "result": result})

    if run_migrate:
        subprocess.check_call(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=ROOT,
        )
        _append("migrate", {"status": "ok"})
    else:
        _append("migrate", "skipped")

    if run_poll:
        _append("poll", await run_poll_standalone(settings))
    else:
        _append("poll", "skipped")

    if run_sync_documents:
        _append(
            "sync-documents",
            await sync_documents_standalone(settings, meeting_external_id=meeting_external_id),
        )
    else:
        _append("sync-documents", "skipped")

    if run_extract_documents:
        _append(
            "extract-documents",
            await extract_documents_standalone(
                settings,
                limit=extract_limit,
                artifact_id=None,
                status_filter=extract_status,
            ),
        )
    else:
        _append("extract-documents", "skipped")

    if run_embed_run:
        _append(
            "embed-run",
            await embed_run_standalone(
                settings,
                enqueue_only=embed_enqueue_only,
                process_only=embed_process_only,
                enqueue_limit=embed_enqueue_limit,
                process_limit=embed_process_limit,
            ),
        )
    else:
        _append("embed-run", "skipped")

    return out
