"""Ordered ingestion pipeline: migrate → poll → sync-documents → extract-documents → embed-run."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Literal, TypedDict

from citycouncil.config import Settings, get_settings
from citycouncil.ingest.documents_extract import extract_documents_standalone
from citycouncil.ingest.documents_sync import sync_documents_standalone
from citycouncil.ingest.embed_jobs import embed_run_standalone
from citycouncil.ingest.poller import run_poll_standalone

ROOT = Path(__file__).resolve().parents[1]

PipelineStepId = Literal[
    "migrate",
    "poll",
    "sync-documents",
    "extract-documents",
    "embed-run",
]

STEP_MIGRATE: PipelineStepId = "migrate"
STEP_POLL: PipelineStepId = "poll"
STEP_SYNC_DOCUMENTS: PipelineStepId = "sync-documents"
STEP_EXTRACT_DOCUMENTS: PipelineStepId = "extract-documents"
STEP_EMBED_RUN: PipelineStepId = "embed-run"


class MigrateStepOk(TypedDict):
    status: Literal["ok"]


class PipelineStepRecord(TypedDict):
    step: PipelineStepId
    result: object


class PipelineRunResult(TypedDict):
    steps: list[PipelineStepRecord]


def _alembic_upgrade_head() -> None:
    subprocess.check_call(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
    )


def _append_migrate_step(steps: list[PipelineStepRecord], enabled: bool) -> None:
    if enabled:
        _alembic_upgrade_head()
        ok: MigrateStepOk = {"status": "ok"}
        steps.append({"step": STEP_MIGRATE, "result": ok})
    else:
        steps.append({"step": STEP_MIGRATE, "result": "skipped"})


async def _append_async_step(
    steps: list[PipelineStepRecord],
    name: PipelineStepId,
    enabled: bool,
    coro_factory: Callable[[], Awaitable[Any]],
) -> None:
    if enabled:
        steps.append({"step": name, "result": await coro_factory()})
    else:
        steps.append({"step": name, "result": "skipped"})


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
) -> PipelineRunResult:
    """Run CLI ingestion steps in a fixed order (see module docstring).

    Each step uses the same standalone helpers as the individual ``citycouncil`` subcommands.
    """
    if embed_enqueue_only and embed_process_only:
        raise ValueError("Cannot combine enqueue-only and process-only")
    settings = settings or get_settings()
    steps: list[PipelineStepRecord] = []

    _append_migrate_step(steps, run_migrate)

    await _append_async_step(
        steps,
        STEP_POLL,
        run_poll,
        lambda: run_poll_standalone(settings),
    )
    await _append_async_step(
        steps,
        STEP_SYNC_DOCUMENTS,
        run_sync_documents,
        lambda: sync_documents_standalone(settings, meeting_external_id=meeting_external_id),
    )
    await _append_async_step(
        steps,
        STEP_EXTRACT_DOCUMENTS,
        run_extract_documents,
        lambda: extract_documents_standalone(
            settings,
            limit=extract_limit,
            artifact_id=None,
            status_filter=extract_status,
        ),
    )
    await _append_async_step(
        steps,
        STEP_EMBED_RUN,
        run_embed_run,
        lambda: embed_run_standalone(
            settings,
            enqueue_only=embed_enqueue_only,
            process_only=embed_process_only,
            enqueue_limit=embed_enqueue_limit,
            process_limit=embed_process_limit,
        ),
    )

    return {"steps": steps}


__all__ = [
    "STEP_EMBED_RUN",
    "STEP_EXTRACT_DOCUMENTS",
    "STEP_MIGRATE",
    "STEP_POLL",
    "STEP_SYNC_DOCUMENTS",
    "run_pipeline_standalone",
]
