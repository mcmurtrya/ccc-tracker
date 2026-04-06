"""Unit tests for CSV/JSON builders in :mod:`citycouncil.export_data` (no DB)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from citycouncil.db.models import VotePosition
from citycouncil.export_data import (
    meetings_json,
    ordinances_csv,
    ordinances_json,
    vote_members_csv,
    vote_members_json,
    votes_csv,
    votes_json,
)


def _dt() -> datetime:
    return datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_meetings_json_one_row() -> None:
    mid = uuid4()
    m = SimpleNamespace(
        id=mid,
        external_id="ext-1",
        meeting_date=date(2026, 2, 1),
        body="Committee",
        location="Hall",
        status="Scheduled",
        created_at=_dt(),
        updated_at=_dt(),
    )
    out = meetings_json([m])
    assert out["count"] == 1
    assert out["items"][0]["id"] == str(mid)
    assert out["items"][0]["external_id"] == "ext-1"


def test_ordinances_csv_and_json() -> None:
    oid = uuid4()
    o = SimpleNamespace(
        id=oid,
        external_id="ord-1",
        title="An ordinance",
        sponsor_external_id="s1",
        introduced_date=date(2026, 3, 1),
        topic_tags=["a", "b"],
        created_at=_dt(),
        updated_at=_dt(),
    )
    assert b"An ordinance" in ordinances_csv([o])
    j = ordinances_json([o])
    assert j["items"][0]["title"] == "An ordinance"


def test_votes_csv_and_json() -> None:
    vid, mid, oid = uuid4(), uuid4(), uuid4()
    meet = SimpleNamespace(external_id="meet-ext")
    ord_ = SimpleNamespace(external_id="ord-ext")
    v = SimpleNamespace(
        id=vid,
        external_id="ve",
        meeting_id=mid,
        ordinance_id=oid,
        meeting=meet,
        ordinance=ord_,
        result="Adopted",
        ayes=10,
        nays=1,
        abstentions=0,
        created_at=_dt(),
    )
    assert b"meet-ext" in votes_csv([v])
    j = votes_json([v])
    assert j["items"][0]["result"] == "Adopted"


def test_vote_members_roundtrip() -> None:
    vid = uuid4()
    meet = SimpleNamespace(external_id="mx")
    ord_ = SimpleNamespace(external_id="ox")
    v = SimpleNamespace(
        id=vid,
        external_id="vx",
        meeting_id=uuid4(),
        ordinance_id=uuid4(),
        meeting=meet,
        ordinance=ord_,
    )
    mem = SimpleNamespace(external_id="mem1", name="Alder", ward=5)
    vm = SimpleNamespace(
        member_id=uuid4(),
        member=mem,
        vote=v,
        position=VotePosition.aye,
    )
    assert b"Alder" in vote_members_csv([vm])
    j = vote_members_json([vm])
    assert j["items"][0]["position"] == "aye"
