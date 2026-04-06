"""Tests for :func:`citycouncil.documents_stats.document_artifact_stats`."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from citycouncil.db.models import ParseStatus
from citycouncil.documents_stats import document_artifact_stats


@pytest.mark.asyncio
async def test_document_artifact_stats_counts() -> None:
    """Scalar sequence: totals, four parse statuses, needs_review, local, embedded, llm pending."""
    session = AsyncMock()
    session.scalar = AsyncMock(
        side_effect=[
            10,
            25,
            1,
            0,
            2,
            0,
            3,
            4,
            5,
            6,
        ]
    )
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
