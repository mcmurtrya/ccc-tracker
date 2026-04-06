"""Hugging Face Inference chat-router HTTP calls."""

from __future__ import annotations

from typing import TypedDict

import httpx

from citycouncil.config import Settings


class ChatMessage(TypedDict):
    role: str
    content: str


async def huggingface_chat_completion(
    settings: Settings,
    messages: list[ChatMessage],
) -> str:
    """POST to ``huggingface_chat_router_url`` and return assistant message text."""
    hf_tok = settings.huggingface_token_value()
    if not hf_tok:
        raise ValueError("CITYCOUNCIL_HUGGINGFACE_TOKEN is not set")

    async with httpx.AsyncClient(timeout=settings.huggingface_chat_timeout) as client:
        r = await client.post(
            settings.huggingface_chat_router_url,
            headers={
                "Authorization": f"Bearer {hf_tok}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.huggingface_chat_model,
                "messages": messages,
                "max_tokens": settings.huggingface_chat_max_tokens,
                "temperature": 0.2,
            },
        )
        r.raise_for_status()
        data = r.json()
        return str(data["choices"][0]["message"]["content"])
