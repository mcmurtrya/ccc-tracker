"""Public read-only ordinance payload."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from citycouncil.db.models import Ordinance


async def fetch_ordinance_public(session: AsyncSession, ordinance_id: UUID) -> dict[str, object] | None:
    q = await session.execute(select(Ordinance).where(Ordinance.id == ordinance_id))
    o = q.scalar_one_or_none()
    if o is None:
        return None
    summarized_at = o.llm_summarized_at.isoformat() if o.llm_summarized_at else None
    return {
        "id": str(o.id),
        "external_id": o.external_id,
        "title": o.title,
        "sponsor_external_id": o.sponsor_external_id,
        "introduced_date": o.introduced_date.isoformat() if o.introduced_date else None,
        "topic_tags": o.topic_tags,
        "llm_summary": o.llm_summary,
        "llm_tags": o.llm_tags,
        "llm_summary_model": o.llm_summary_model,
        "llm_summary_prompt_version": o.llm_summary_prompt_version,
        "llm_summarized_at": summarized_at,
    }
