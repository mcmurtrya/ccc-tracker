"""Unit tests for Hugging Face embeddings helper (no network)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from citycouncil.ingest.embeddings_huggingface import (
    _parse_embedding_body,
    embed_texts_huggingface_batch,
)


def test_parse_single_flat_vector() -> None:
    assert _parse_embedding_body([0.1, 0.2, 0.3]) == [[0.1, 0.2, 0.3]]


def test_parse_batch() -> None:
    assert _parse_embedding_body([[0.1], [0.2]]) == [[0.1], [0.2]]


def test_parse_rejects_error_dict() -> None:
    with pytest.raises(ValueError, match="rate"):
        _parse_embedding_body({"error": "rate limited"})


def test_embed_texts_huggingface_batch_empty() -> None:
    assert embed_texts_huggingface_batch([], api_token="t", model="m") == []


def test_embed_texts_huggingface_batch_raises_without_token() -> None:
    with pytest.raises(ValueError, match="empty"):
        embed_texts_huggingface_batch(["a"], api_token="", model="m")


@patch("citycouncil.ingest.embeddings_huggingface.httpx.post")
def test_embed_texts_huggingface_batch_batch_response(mock_post: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = [[0.1] * 384, [0.2] * 384]
    mock_resp.raise_for_status = MagicMock()
    mock_post.return_value = mock_resp

    out = embed_texts_huggingface_batch(
        ["a", "b"],
        api_token="hf_test",
        model="sentence-transformers/all-MiniLM-L6-v2",
        expected_dimensions=384,
    )
    assert len(out) == 2
    assert len(out[0]) == 384
    mock_post.assert_called_once()
    url = mock_post.call_args[0][0]
    assert "sentence-transformers/all-MiniLM-L6-v2" in url
    assert "feature-extraction" in url


@patch("citycouncil.ingest.embeddings_huggingface.httpx.post")
def test_embed_texts_huggingface_batch_truncates(mock_post: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = [[0.0] * 384]
    mock_resp.raise_for_status = MagicMock()
    mock_post.return_value = mock_resp

    long = "x" * 50_000
    embed_texts_huggingface_batch(
        [long],
        api_token="t",
        model="m",
        expected_dimensions=384,
        input_max_chars=100,
    )
    sent = mock_post.call_args[1]["json"]["inputs"][0]
    assert len(sent) == 100
