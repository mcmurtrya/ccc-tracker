"""Tests for :func:`citycouncil.documents_stats.document_artifact_stats`."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from citycouncil.db.models import ParseStatus
from citycouncil.documents_stats import document_artifact_stats


@pytest.mark.asyncio
async def test_document_artifact_stats_counts() -> None:
    """Three queries: artifact aggregates, chunk aggregates, LLM pending."""
    artifact_row = SimpleNamespace(
        artifacts_total=10,
        needs_review=3,
        with_local=4,
        ps_pending=1,
        ps_processing=0,
        ps_ok=2,
        ps_failed=0,
    )
    chunk_row = SimpleNamespace(chunks_total=25, chunks_embedded=5)

    exec_artifact = MagicMock()
    exec_artifact.one.return_value = artifact_row
    exec_chunk = MagicMock()
    exec_chunk.one.return_value = chunk_row

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[exec_artifact, exec_chunk])
    session.scalar = AsyncMock(return_value=6)

    out = await document_artifact_stats(session)
    assert out["document_artifacts_total"] == 10
    assert out["document_chunks_total"] == 25
    assert out["by_parse_status"][ParseStatus.pending.value] == 1
    assert out["by_parse_status"][ParseStatus.processing.value] == 0
    assert out["by_parse_status"][ParseStatus.ok.value] == 2
    assert out["by_parse_status"][ParseStatus.failed.value] == 0
    assert out["needs_review"] == 3
    assert out["artifacts_with_local_path"] == 4
    assert out["document_chunks_with_embedding"] == 5
    assert out["llm_jobs_pending"] == 6
    assert session.execute.await_count == 2
    assert session.scalar.await_count == 1
