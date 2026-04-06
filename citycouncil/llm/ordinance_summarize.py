"""Ordinance summary + tags via Hugging Face Inference chat (LLM-202)."""

from __future__ import annotations

import json
import re
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from citycouncil.config import Settings
from citycouncil.db.models import Ordinance, utc_now


def _extract_json_object(text: str) -> dict[str, Any]:
    t = text.strip()
    fence = re.match(r"^```(?:json)?\s*([\s\S]*?)```\s*$", t)
    if fence:
        t = fence.group(1).strip()
    return json.loads(t)


async def summarize_ordinance(
    session: AsyncSession,
    settings: Settings,
    ordinance_id: UUID,
) -> dict[str, Any]:
    """Fill ``ordinance.llm_summary`` and ``ordinance.llm_tags`` from HF chat."""
    if not settings.huggingface_token:
        raise ValueError("CITYCOUNCIL_HUGGINGFACE_TOKEN is not set")

    q = await session.execute(select(Ordinance).where(Ordinance.id == ordinance_id))
    ord_row = q.scalar_one_or_none()
    if ord_row is None:
        raise ValueError(f"ordinance not found: {ordinance_id}")

    system = (
        "Respond with a single JSON object only, no markdown, no commentary. "
        'Schema: {"summary": string (2-4 sentences), "tags": string[] (up to 8 short topical tags)}'
    )
    payload_preview = json.dumps(ord_row.raw_json or {}, default=str)[:8000]
    user = f"Title:\n{ord_row.title}\n\nContext (JSON, may be truncated):\n{payload_preview}"

    async with httpx.AsyncClient(timeout=settings.huggingface_chat_timeout) as client:
        r = await client.post(
            settings.huggingface_chat_router_url,
            headers={
                "Authorization": f"Bearer {settings.huggingface_token}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.huggingface_chat_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": settings.huggingface_chat_max_tokens,
                "temperature": 0.2,
            },
        )
    r.raise_for_status()
    data = r.json()
    content = data["choices"][0]["message"]["content"]
    parsed = _extract_json_object(content)
    summary = str(parsed.get("summary", "")).strip()
    tags_raw = parsed.get("tags")
    tags: list[str] = []
    if isinstance(tags_raw, list):
        tags = [str(x).strip() for x in tags_raw if str(x).strip()][:8]

    ord_row.llm_summary = summary or None
    ord_row.llm_tags = tags or None
    ord_row.llm_summary_model = settings.huggingface_chat_model
    ord_row.llm_summary_prompt_version = settings.llm_summarize_prompt_version
    ord_row.llm_summarized_at = utc_now()
    await session.flush()

    return {
        "ordinance_id": str(ord_row.id),
        "external_id": ord_row.external_id,
        "llm_summary": ord_row.llm_summary,
        "llm_tags": ord_row.llm_tags,
        "llm_summary_model": ord_row.llm_summary_model,
        "llm_summary_prompt_version": ord_row.llm_summary_prompt_version,
        "llm_summarized_at": ord_row.llm_summarized_at.isoformat() if ord_row.llm_summarized_at else None,
    }
