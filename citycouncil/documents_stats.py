"""Aggregates for :class:`~citycouncil.db.models.DocumentArtifact` / :class:`~citycouncil.db.models.DocumentChunk`."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from citycouncil.db.models import DocumentArtifact, DocumentChunk, LlmJob, ParseStatus


async def document_artifact_stats(session: AsyncSession) -> dict[str, Any]:
    """Counts for DOC-005 admin/metrics."""
    total_docs = await session.scalar(select(func.count()).select_from(DocumentArtifact))
    total_chunks = await session.scalar(select(func.count()).select_from(DocumentChunk))
    by_status: dict[str, int] = {}
    for ps in ParseStatus:
        c = await session.scalar(
            select(func.count()).where(DocumentArtifact.parse_status == ps)
        )
        by_status[ps.value] = int(c or 0)
    needs_review = await session.scalar(
        select(func.count()).where(DocumentArtifact.needs_review.is_(True))
    )
    with_local = await session.scalar(
        select(func.count()).where(DocumentArtifact.local_path.isnot(None))
    )
    chunks_embedded = await session.scalar(
        select(func.count()).where(DocumentChunk.embedding.isnot(None))
    )
    llm_jobs_pending = await session.scalar(
        select(func.count()).where(LlmJob.status == "pending")
    )
    return {
        "document_artifacts_total": int(total_docs or 0),
        "document_chunks_total": int(total_chunks or 0),
        "document_chunks_with_embedding": int(chunks_embedded or 0),
        "needs_review": int(needs_review or 0),
        "artifacts_with_local_path": int(with_local or 0),
        "llm_jobs_pending": int(llm_jobs_pending or 0),
        "by_parse_status": by_status,
    }
