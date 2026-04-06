"""Enqueue and process ``embed_chunk`` jobs via Hugging Face feature-extraction (LLM-201 / LLM-203)."""

from __future__ import annotations

import asyncio
import logging
from typing import TypedDict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from citycouncil.config import Settings, get_settings
from citycouncil.constants import PGVECTOR_EMBEDDING_DIMENSION
from citycouncil.db.models import DocumentChunk, LlmJob, utc_now
from citycouncil.db.session import standalone_session
from citycouncil.ingest.embeddings_huggingface import embed_texts_huggingface_batch
from citycouncil.ingest.hf_embedding_params import hf_feature_extraction_call_kwargs

logger = logging.getLogger(__name__)

JOB_EMBED_CHUNK = "embed_chunk"


class EmbedProcessStats(TypedDict):
    """Counters returned by :func:`process_embed_jobs`."""

    jobs_fetched: int
    jobs_ok: int
    jobs_failed: int
    batches: int


class EmbedRunStandaloneResult(TypedDict):
    """Return value of :func:`embed_run_standalone`."""

    enqueued: int
    process: EmbedProcessStats | None
    enqueue_only: bool
    process_only: bool


def _mark_embed_job_failed(job: LlmJob, msg: str, stats: EmbedProcessStats) -> None:
    job.status = "failed"
    job.error = msg
    stats["jobs_failed"] += 1


async def _pending_embed_chunk_ids(session: AsyncSession) -> set[str]:
    q = await session.execute(
        select(LlmJob.payload).where(
            LlmJob.job_type == JOB_EMBED_CHUNK,
            LlmJob.status == "pending",
        )
    )
    out: set[str] = set()
    for (payload,) in q.all():
        if isinstance(payload, dict):
            cid = payload.get("chunk_id")
            if cid is not None:
                out.add(str(cid))
    return out


async def enqueue_embed_jobs(session: AsyncSession, settings: Settings) -> int:
    """Create ``embed_chunk`` jobs for chunks with no embedding (skips empty body)."""
    pending_ids = await _pending_embed_chunk_ids(session)
    cap = settings.embed_enqueue_limit
    stmt = (
        select(DocumentChunk)
        .where(DocumentChunk.embedding.is_(None))
        .where(DocumentChunk.body != "")
        .order_by(DocumentChunk.created_at.asc())
        .limit(max(cap * 4, cap))
    )
    q = await session.execute(stmt)
    rows = list(q.scalars().all())
    enqueued = 0
    for chunk in rows:
        if enqueued >= cap:
            break
        cid = str(chunk.id)
        if cid in pending_ids:
            continue
        session.add(
            LlmJob(
                job_type=JOB_EMBED_CHUNK,
                status="pending",
                payload={"chunk_id": cid},
            )
        )
        pending_ids.add(cid)
        enqueued += 1
    await session.flush()
    return enqueued


async def _fetch_pending_jobs(session: AsyncSession, limit: int) -> list[LlmJob]:
    stmt = (
        select(LlmJob)
        .where(LlmJob.job_type == JOB_EMBED_CHUNK, LlmJob.status == "pending")
        .order_by(LlmJob.created_at.asc())
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    q = await session.execute(stmt)
    return list(q.scalars().all())


async def _collect_embed_work(
    session: AsyncSession,
    batch: list[LlmJob],
    stats: EmbedProcessStats,
) -> list[tuple[LlmJob, DocumentChunk]]:
    """Resolve jobs to ``(job, chunk)`` pairs that still need embedding."""
    work: list[tuple[LlmJob, DocumentChunk]] = []
    for job in batch:
        raw = job.payload.get("chunk_id") if isinstance(job.payload, dict) else None
        if raw is None:
            _mark_embed_job_failed(job, "payload missing chunk_id", stats)
            continue
        try:
            cid = UUID(str(raw))
        except ValueError as e:
            _mark_embed_job_failed(job, f"invalid chunk_id: {e}", stats)
            continue
        ch = await session.get(DocumentChunk, cid)
        if ch is None:
            _mark_embed_job_failed(job, "document_chunks row not found", stats)
            continue
        if ch.embedding is not None:
            job.status = "ok"
            job.result = {"chunk_id": str(ch.id), "skipped": "already_embedded"}
            stats["jobs_ok"] += 1
            continue
        work.append((job, ch))
    return work


async def process_embed_jobs(session: AsyncSession, settings: Settings) -> EmbedProcessStats:
    """Process pending ``embed_chunk`` jobs (batched embedding HTTP calls)."""
    if not settings.huggingface_token_value():
        raise ValueError("CITYCOUNCIL_HUGGINGFACE_TOKEN is not set (see embeddings_huggingface.py)")
    model = settings.huggingface_embedding_model
    batch_size = settings.embed_batch_size
    proc_limit = settings.embed_process_limit
    embed_kw = hf_feature_extraction_call_kwargs(settings, for_query=False)

    stats: EmbedProcessStats = {
        "jobs_fetched": 0,
        "jobs_ok": 0,
        "jobs_failed": 0,
        "batches": 0,
    }

    jobs = await _fetch_pending_jobs(session, proc_limit)
    stats["jobs_fetched"] = len(jobs)
    if not jobs:
        return stats

    for job in jobs:
        job.status = "running"
        job.error = None
    await session.flush()

    for i in range(0, len(jobs), batch_size):
        batch = jobs[i : i + batch_size]
        stats["batches"] += 1
        work = await _collect_embed_work(session, batch, stats)
        if not work:
            continue
        texts = [ch.body or "" for _, ch in work]
        try:
            vectors = await asyncio.to_thread(
                embed_texts_huggingface_batch,
                texts,
                **embed_kw,
            )
        except Exception as e:
            logger.warning("embed batch failed: %s", e)
            err = str(e)[:8000]
            for job, _ in work:
                job.status = "failed"
                job.error = err
            stats["jobs_failed"] += len(work)
            continue

        now = utc_now()
        for (job, ch), vec in zip(work, vectors, strict=True):
            ch.embedding = vec
            if len(vec) == PGVECTOR_EMBEDDING_DIMENSION:
                ch.embedding_vector = vec
            ch.embedding_model = model
            ch.embedded_at = now
            job.status = "ok"
            job.result = {"chunk_id": str(ch.id), "dimensions": len(vec)}
            job.error = None
            stats["jobs_ok"] += 1

    await session.flush()
    return stats


async def embed_run_standalone(
    settings: Settings | None = None,
    *,
    enqueue_only: bool = False,
    process_only: bool = False,
    enqueue_limit: int | None = None,
    process_limit: int | None = None,
) -> EmbedRunStandaloneResult:
    """Enqueue and/or process embedding jobs (Hugging Face Inference)."""
    base = settings or get_settings()
    upd: dict[str, int] = {}
    if enqueue_limit is not None:
        upd["embed_enqueue_limit"] = enqueue_limit
    if process_limit is not None:
        upd["embed_process_limit"] = process_limit
    settings = base.model_copy(update=upd) if upd else base

    out: EmbedRunStandaloneResult = {
        "enqueued": 0,
        "process": None,
        "enqueue_only": enqueue_only,
        "process_only": process_only,
    }
    async with standalone_session(settings) as session:
        if not process_only:
            out["enqueued"] = await enqueue_embed_jobs(session, settings)
        if not enqueue_only:
            out["process"] = await process_embed_jobs(session, settings)
        await session.commit()
    return out
