"""Aggregates for :class:`~citycouncil.db.models.DocumentArtifact` / :class:`~citycouncil.db.models.DocumentChunk`."""

from __future__ import annotations

from typing import TypedDict

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from citycouncil.db.models import DocumentArtifact, DocumentChunk, LlmJob, ParseStatus


class DocumentArtifactStats(TypedDict):
    """DOC-005 admin/metrics payload."""

    document_artifacts_total: int
    document_chunks_total: int
    document_chunks_with_embedding: int
    needs_review: int
    artifacts_with_local_path: int
    llm_jobs_pending: int
    by_parse_status: dict[str, int]


def _artifact_aggregate_select():
    cols = [
        func.count().label("artifacts_total"),
        func.coalesce(
            func.sum(case((DocumentArtifact.needs_review.is_(True), 1), else_=0)),
            0,
        ).label("needs_review"),
        func.coalesce(
            func.sum(case((DocumentArtifact.local_path.isnot(None), 1), else_=0)),
            0,
        ).label("with_local"),
    ]
    for ps in ParseStatus:
        cols.append(
            func.coalesce(
                func.sum(case((DocumentArtifact.parse_status == ps, 1), else_=0)),
                0,
            ).label(f"ps_{ps.value}")
        )
    return select(*cols)


def _chunk_aggregate_select():
    return select(
        func.count().label("chunks_total"),
        func.coalesce(
            func.sum(case((DocumentChunk.embedding.isnot(None), 1), else_=0)),
            0,
        ).label("chunks_embedded"),
    )


async def document_artifact_stats(session: AsyncSession) -> DocumentArtifactStats:
    """Counts for DOC-005 admin/metrics (three round-trips: artifacts, chunks, LLM jobs)."""
    ar = (await session.execute(_artifact_aggregate_select())).one()
    cr = (await session.execute(_chunk_aggregate_select())).one()
    llm_pending = await session.scalar(select(func.count()).where(LlmJob.status == "pending"))

    by_status = {ps.value: int(getattr(ar, f"ps_{ps.value}")) for ps in ParseStatus}

    return {
        "document_artifacts_total": int(ar.artifacts_total),
        "document_chunks_total": int(cr.chunks_total),
        "document_chunks_with_embedding": int(cr.chunks_embedded),
        "needs_review": int(ar.needs_review),
        "artifacts_with_local_path": int(ar.with_local),
        "llm_jobs_pending": int(llm_pending or 0),
        "by_parse_status": by_status,
    }
