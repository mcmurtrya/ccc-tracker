"""Unit tests for :mod:`citycouncil.ordinance_public`."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from citycouncil.ordinance_public import fetch_ordinance_public


@pytest.mark.asyncio
async def test_fetch_ordinance_public_not_found() -> None:
    oid = uuid.uuid4()
    r = MagicMock()
    r.scalar_one_or_none.return_value = None
    session = AsyncMock()
    session.execute = AsyncMock(return_value=r)
    assert await fetch_ordinance_public(session, oid) is None


@pytest.mark.asyncio
async def test_fetch_ordinance_public_found() -> None:
    oid = uuid.uuid4()
    ts = datetime(2024, 3, 15, 12, 0, tzinfo=timezone.utc)
    o = SimpleNamespace(
        id=oid,
        external_id="ord-1",
        title="An ordinance",
        sponsor_external_id="s1",
        introduced_date=date(2024, 1, 10),
        topic_tags=["zoning"],
        llm_summary="sum",
        llm_tags=["tag"],
        llm_summary_model="m",
        llm_summary_prompt_version="v1",
        llm_summarized_at=ts,
    )
    r = MagicMock()
    r.scalar_one_or_none.return_value = o
    session = AsyncMock()
    session.execute = AsyncMock(return_value=r)
    out = await fetch_ordinance_public(session, oid)
    assert out is not None
    assert out["id"] == str(oid)
    assert out["external_id"] == "ord-1"
    assert out["introduced_date"] == "2024-01-10"
    assert out["llm_summarized_at"] == ts.isoformat()


@pytest.mark.asyncio
async def test_fetch_ordinance_public_null_dates_and_summary_fields() -> None:
    oid = uuid.uuid4()
    o = SimpleNamespace(
        id=oid,
        external_id="x",
        title="t",
        sponsor_external_id=None,
        introduced_date=None,
        topic_tags=None,
        llm_summary=None,
        llm_tags=None,
        llm_summary_model=None,
        llm_summary_prompt_version=None,
        llm_summarized_at=None,
    )
    r = MagicMock()
    r.scalar_one_or_none.return_value = o
    session = AsyncMock()
    session.execute = AsyncMock(return_value=r)
    out = await fetch_ordinance_public(session, oid)
    assert out is not None
    assert out["introduced_date"] is None
    assert out["llm_summarized_at"] is None
