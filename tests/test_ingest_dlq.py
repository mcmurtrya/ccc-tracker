"""Tests for :mod:`citycouncil.ingest.dlq`."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession

from citycouncil.ingest.dlq import record_dlq


@pytest.mark.asyncio
async def test_record_dlq_adds_row_and_truncates_error() -> None:
    session = MagicMock(spec=AsyncSession)
    session.flush = AsyncMock()
    long_err = "e" * 30_000
    await record_dlq(session, "elms", {"k": 1}, long_err)
    session.add.assert_called_once()
    session.flush.assert_awaited_once()
    row = session.add.call_args[0][0]
    assert row.source == "elms"
    assert row.payload == {"k": 1}
    assert len(row.error) == 20_000
