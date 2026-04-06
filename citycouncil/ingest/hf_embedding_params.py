"""Shared Hugging Face feature-extraction parameters from :class:`~citycouncil.config.Settings`."""

from __future__ import annotations

from typing import Any

from citycouncil.config import Settings


def hf_feature_extraction_call_kwargs(settings: Settings, *, for_query: bool = False) -> dict[str, Any]:
    """Keyword arguments for :func:`~citycouncil.ingest.embeddings_huggingface.embed_texts_huggingface_batch` (except ``texts``).

    ``for_query=True`` uses ``huggingface_search_prompt_name``; otherwise chunk indexing uses
    ``huggingface_prompt_name``.
    """
    prompt = (
        settings.huggingface_search_prompt_name
        if for_query
        else settings.huggingface_prompt_name
    )
    return {
        "api_token": settings.huggingface_token or "",
        "model": settings.huggingface_embedding_model,
        "expected_dimensions": settings.embedding_dimensions,
        "normalize": settings.huggingface_normalize_embeddings,
        "prompt_name": prompt,
        "timeout": 120.0,
        "input_max_chars": settings.embed_input_max_chars,
        "inference_base_url": settings.huggingface_inference_base_url,
    }
