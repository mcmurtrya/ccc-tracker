"""Public read-only ordinance payload for residents / reporters."""

from __future__ import annotations

from typing import TypedDict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from citycouncil.db.models import Ordinance


class OrdinancePublicPayload(TypedDict):
    id: str
    external_id: str
    title: str
    sponsor_external_id: str | None
    introduced_date: str | None
    topic_tags: list[str] | None
    llm_summary: str | None
    llm_tags: list[str] | None
    llm_summary_model: str | None
    llm_summary_prompt_version: str | None
    llm_summarized_at: str | None


async def fetch_ordinance_public(
    session: AsyncSession, ordinance_id: UUID
) -> OrdinancePublicPayload | None:
    """Return public JSON for one ordinance, or ``None`` if not found."""
    q = await session.execute(select(Ordinance).where(Ordinance.id == ordinance_id))
    o = q.scalar_one_or_none()
    if o is None:
        return None
    summarized_at = o.llm_summarized_at.isoformat() if o.llm_summarized_at else None
    payload: OrdinancePublicPayload = {
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
    return payload
