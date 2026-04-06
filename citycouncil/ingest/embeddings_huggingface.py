"""Hugging Face Inference feature extraction (embeddings) via HTTP (LLM-203).

Uses the serverless router endpoint documented for embedding models, e.g.
``https://router.huggingface.co/hf-inference/models/<model>/pipeline/feature-extraction``.

Requires a Hugging Face token with permission to call Inference Providers.
"""

from __future__ import annotations

from typing import Any

import httpx

DEFAULT_INFERENCE_BASE = "https://router.huggingface.co/hf-inference"


def _feature_extraction_url(model: str, base_url: str) -> str:
    # Model id may contain slashes (org/name); use as path segments, not one encoded segment.
    return f"{base_url.rstrip('/')}/models/{model}/pipeline/feature-extraction"


def _parse_embedding_body(body: Any) -> list[list[float]]:
    """Normalize HF feature-extraction JSON to a list of float vectors."""
    if body is None:
        raise ValueError("empty embedding response")
    if isinstance(body, dict) and "error" in body:
        raise ValueError(str(body.get("error")))
    if not isinstance(body, list):
        raise ValueError(f"unexpected embedding response type: {type(body)}")
    if not body:
        return []
    # Single sentence vector: [float, float, ...]
    if isinstance(body[0], (int, float)):
        return [[float(x) for x in body]]
    out: list[list[float]] = []
    for row in body:
        if isinstance(row, list) and row and isinstance(row[0], (int, float)):
            out.append([float(x) for x in row])
        else:
            raise ValueError("unexpected nested embedding shape")
    return out


def embed_texts_huggingface_batch(
    texts: list[str],
    *,
    api_token: str,
    model: str,
    expected_dimensions: int | None = None,
    normalize: bool = True,
    prompt_name: str | None = None,
    truncate: bool = True,
    timeout: float = 120.0,
    input_max_chars: int = 12_000,
    inference_base_url: str = DEFAULT_INFERENCE_BASE,
) -> list[list[float]]:
    """Return one embedding vector per input string (same order as ``texts``)."""
    if not texts:
        return []
    if not api_token:
        raise ValueError("huggingface_token is empty")
    trimmed = [t[:input_max_chars] if t else "" for t in texts]
    url = _feature_extraction_url(model, inference_base_url)
    payload: dict[str, Any] = {"inputs": trimmed, "normalize": normalize, "truncate": truncate}
    if prompt_name is not None:
        payload["prompt_name"] = prompt_name
    r = httpx.post(
        url,
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )
    r.raise_for_status()
    body = r.json()
    vectors = _parse_embedding_body(body)
    if len(vectors) != len(texts):
        raise ValueError(f"embedding count mismatch: got {len(vectors)}, expected {len(texts)}")
    for v in vectors:
        if expected_dimensions is not None and len(v) != expected_dimensions:
            raise ValueError(
                f"embedding dim mismatch: got {len(v)}, expected {expected_dimensions} "
                "(set CITYCOUNCIL_EMBEDDING_DIMENSIONS to the model output size)"
            )
    return vectors
