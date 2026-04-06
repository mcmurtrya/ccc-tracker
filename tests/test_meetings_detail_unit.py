"""Unit tests for :mod:`citycouncil.meetings_detail` payload builders and fetch."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from citycouncil.db.models import ParseStatus, VotePosition
from citycouncil.meetings_detail import (
    _agenda_item_payload,
    _document_payload,
    _vote_payload,
    fetch_meeting_detail,
)


def test_agenda_item_payload_without_ordinance() -> None:
    aid = uuid.uuid4()
    a = SimpleNamespace(
        id=aid,
        sequence=2,
        raw_text="item",
        ordinance_id=None,
        ordinance=None,
    )
    out = _agenda_item_payload(a)
    assert out["id"] == str(aid)
    assert out["sequence"] == 2
    assert out["ordinance"] is None


def test_agenda_item_payload_with_ordinance() -> None:
    oid = uuid.uuid4()
    ord_obj = SimpleNamespace(
        id=oid,
        external_id="eo",
        title="Title",
        introduced_date=date(2024, 4, 1),
        topic_tags=["a"],
        llm_summary="s",
        llm_tags=["b"],
    )
    a = SimpleNamespace(
        id=uuid.uuid4(),
        sequence=1,
        raw_text="r",
        ordinance_id=oid,
        ordinance=ord_obj,
    )
    out = _agenda_item_payload(a)
    assert out["ordinance"]["title"] == "Title"
    assert out["ordinance"]["introduced_date"] == "2024-04-01"


def test_vote_payload_sorts_roll_by_member_name() -> None:
    oid = uuid.uuid4()
    ord_obj = SimpleNamespace(id=oid, external_id="e", title="T")
    m_zed = SimpleNamespace(id=uuid.uuid4(), name="Zed", ward=1)
    m_alice = SimpleNamespace(id=uuid.uuid4(), name="alice", ward=2)
    vm_z = SimpleNamespace(member=m_zed, position=VotePosition.nay)
    vm_a = SimpleNamespace(member=m_alice, position=VotePosition.aye)
    v = SimpleNamespace(
        id=uuid.uuid4(),
        external_id="v1",
        result="pass",
        ayes=2,
        nays=0,
        abstentions=0,
        ordinance=ord_obj,
        vote_members=[vm_z, vm_a],
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    out = _vote_payload(v)
    names = [r["name"] for r in out["roll_call"]]
    assert names == ["alice", "Zed"]
    assert out["roll_call"][0]["position"] == "aye"


def test_document_payload_includes_parse_status_value() -> None:
    did = uuid.uuid4()
    d = SimpleNamespace(
        id=did,
        file_name="x.pdf",
        source_url="https://example.com/x",
        uri="s3://b/x",
        attachment_type="application/pdf",
        parse_status=ParseStatus.failed,
        bytes_size=42,
        needs_review=True,
    )
    out = _document_payload(d)
    assert out["parse_status"] == "failed"
    assert out["needs_review"] is True


@pytest.mark.asyncio
async def test_fetch_meeting_detail_not_found() -> None:
    mid = uuid.uuid4()
    r1 = MagicMock()
    r1.scalar_one_or_none.return_value = None
    session = AsyncMock()
    session.execute = AsyncMock(return_value=r1)
    assert await fetch_meeting_detail(session, mid) is None


@pytest.mark.asyncio
async def test_fetch_meeting_detail_with_documents() -> None:
    mid = uuid.uuid4()
    doc = SimpleNamespace(
        id=uuid.uuid4(),
        file_name="m.pdf",
        source_url=None,
        uri="path",
        attachment_type=None,
        parse_status=ParseStatus.pending,
        bytes_size=None,
        needs_review=False,
    )
    m = SimpleNamespace(
        id=mid,
        external_id="ext",
        meeting_date=date(2025, 1, 20),
        body="council",
        location="city hall",
        status="scheduled",
        agenda_items=[],
        votes=[],
    )
    r1 = MagicMock()
    r1.scalar_one_or_none.return_value = m
    r2 = MagicMock()
    r2.scalars.return_value.all.return_value = [doc]
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[r1, r2])
    out = await fetch_meeting_detail(session, mid)
    assert out is not None
    assert out["meeting"]["external_id"] == "ext"
    assert len(out["documents"]) == 1
    assert out["documents"][0]["file_name"] == "m.pdf"
