"""Ordinance summary + tags via Hugging Face Inference chat (LLM-202)."""

from __future__ import annotations

import json
from typing import TypedDict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from citycouncil.config import Settings
from citycouncil.db.models import Ordinance, utc_now
from citycouncil.llm.hf_chat import ChatMessage, huggingface_chat_completion
from citycouncil.llm.json_response import extract_json_object

SYSTEM_PROMPT_ORDINANCE_SUMMARIZE = (
    "Respond with a single JSON object only, no markdown, no commentary. "
    'Schema: {"summary": string (2-4 sentences), "tags": string[] (up to 8 short topical tags)}'
)


def _user_prompt_ordinance(title: str, payload_preview: str) -> str:
    return f"Title:\n{title}\n\nContext (JSON, may be truncated):\n{payload_preview}"


class SummarizeOrdinanceResult(TypedDict):
    """API / DB shape after summarizing an ordinance."""

    ordinance_id: str
    external_id: str
    llm_summary: str | None
    llm_tags: list[str] | None
    llm_summary_model: str | None
    llm_summary_prompt_version: str | None
    llm_summarized_at: str | None


async def summarize_ordinance(
    session: AsyncSession,
    settings: Settings,
    ordinance_id: UUID,
) -> SummarizeOrdinanceResult:
    """Fill ``ordinance.llm_summary`` and ``ordinance.llm_tags`` from HF chat."""
    hf_tok = settings.huggingface_token_value()
    if not hf_tok:
        raise ValueError("CITYCOUNCIL_HUGGINGFACE_TOKEN is not set")

    q = await session.execute(select(Ordinance).where(Ordinance.id == ordinance_id))
    ord_row = q.scalar_one_or_none()
    if ord_row is None:
        raise ValueError(f"ordinance not found: {ordinance_id}")

    payload_preview = json.dumps(ord_row.raw_json or {}, default=str)[:8000]
    user = _user_prompt_ordinance(ord_row.title, payload_preview)
    messages: list[ChatMessage] = [
        {"role": "system", "content": SYSTEM_PROMPT_ORDINANCE_SUMMARIZE},
        {"role": "user", "content": user},
    ]
    content = await huggingface_chat_completion(settings, messages)
    parsed = extract_json_object(content)
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
