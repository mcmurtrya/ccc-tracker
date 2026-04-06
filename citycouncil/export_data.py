"""Bulk CSV/JSON exports for reporters (admin-only routes)."""

from __future__ import annotations

import csv
from datetime import date, datetime
from io import StringIO
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from citycouncil.db.models import Meeting, Ordinance, Vote, VoteMember


def _dt(v: datetime | None) -> str:
    return v.isoformat() if v else ""


def _d(v: date | None) -> str:
    return v.isoformat() if v else ""


async def load_meetings_ordered(session: AsyncSession) -> list[Meeting]:
    q = await session.execute(select(Meeting).order_by(Meeting.meeting_date.desc()))
    return list(q.scalars().all())


async def load_ordinances_ordered(session: AsyncSession) -> list[Ordinance]:
    q = await session.execute(select(Ordinance).order_by(Ordinance.updated_at.desc()))
    return list(q.scalars().all())


async def load_votes_with_refs(session: AsyncSession) -> list[Vote]:
    q = await session.execute(
        select(Vote)
        .options(selectinload(Vote.meeting), selectinload(Vote.ordinance))
        .order_by(Vote.created_at.desc())
    )
    return list(q.scalars().all())


async def load_vote_members_with_refs(session: AsyncSession) -> list[VoteMember]:
    q = await session.execute(
        select(VoteMember)
        .options(
            selectinload(VoteMember.member),
            selectinload(VoteMember.vote).selectinload(Vote.meeting),
            selectinload(VoteMember.vote).selectinload(Vote.ordinance),
        )
        .order_by(VoteMember.id)
    )
    return list(q.scalars().all())


def meetings_csv(rows: list[Meeting]) -> bytes:
    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "id",
            "external_id",
            "meeting_date",
            "body",
            "location",
            "status",
            "created_at",
            "updated_at",
        ]
    )
    for m in rows:
        w.writerow(
            [
                str(m.id),
                m.external_id,
                _d(m.meeting_date),
                m.body or "",
                m.location or "",
                m.status or "",
                _dt(m.created_at),
                _dt(m.updated_at),
            ]
        )
    return buf.getvalue().encode("utf-8")


def meetings_json(rows: list[Meeting]) -> dict[str, Any]:
    return {
        "count": len(rows),
        "items": [
            {
                "id": str(m.id),
                "external_id": m.external_id,
                "meeting_date": _d(m.meeting_date),
                "body": m.body,
                "location": m.location,
                "status": m.status,
                "created_at": _dt(m.created_at),
                "updated_at": _dt(m.updated_at),
            }
            for m in rows
        ],
    }


def ordinances_csv(rows: list[Ordinance]) -> bytes:
    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "id",
            "external_id",
            "title",
            "sponsor_external_id",
            "introduced_date",
            "topic_tags",
            "created_at",
            "updated_at",
        ]
    )
    for o in rows:
        tags = ",".join(o.topic_tags or []) if o.topic_tags else ""
        w.writerow(
            [
                str(o.id),
                o.external_id,
                o.title,
                o.sponsor_external_id or "",
                _d(o.introduced_date),
                tags,
                _dt(o.created_at),
                _dt(o.updated_at),
            ]
        )
    return buf.getvalue().encode("utf-8")


def ordinances_json(rows: list[Ordinance]) -> dict[str, Any]:
    return {
        "count": len(rows),
        "items": [
            {
                "id": str(o.id),
                "external_id": o.external_id,
                "title": o.title,
                "sponsor_external_id": o.sponsor_external_id,
                "introduced_date": _d(o.introduced_date),
                "topic_tags": o.topic_tags,
                "created_at": _dt(o.created_at),
                "updated_at": _dt(o.updated_at),
            }
            for o in rows
        ],
    }


def votes_csv(rows: list[Vote]) -> bytes:
    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "vote_id",
            "vote_external_id",
            "meeting_id",
            "meeting_external_id",
            "ordinance_id",
            "ordinance_external_id",
            "result",
            "ayes",
            "nays",
            "abstentions",
            "created_at",
        ]
    )
    for v in rows:
        meet = v.meeting
        ord_ = v.ordinance
        w.writerow(
            [
                str(v.id),
                v.external_id or "",
                str(v.meeting_id),
                meet.external_id if meet else "",
                str(v.ordinance_id),
                ord_.external_id if ord_ else "",
                v.result or "",
                v.ayes if v.ayes is not None else "",
                v.nays if v.nays is not None else "",
                v.abstentions if v.abstentions is not None else "",
                _dt(v.created_at),
            ]
        )
    return buf.getvalue().encode("utf-8")


def votes_json(rows: list[Vote]) -> dict[str, Any]:
    out: list[dict[str, Any]] = []
    for v in rows:
        meet = v.meeting
        ord_ = v.ordinance
        out.append(
            {
                "vote_id": str(v.id),
                "vote_external_id": v.external_id,
                "meeting_id": str(v.meeting_id),
                "meeting_external_id": meet.external_id if meet else None,
                "ordinance_id": str(v.ordinance_id),
                "ordinance_external_id": ord_.external_id if ord_ else None,
                "result": v.result,
                "ayes": v.ayes,
                "nays": v.nays,
                "abstentions": v.abstentions,
                "created_at": _dt(v.created_at),
            }
        )
    return {"count": len(out), "items": out}


def vote_members_csv(rows: list[VoteMember]) -> bytes:
    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "vote_id",
            "vote_external_id",
            "meeting_id",
            "meeting_external_id",
            "ordinance_id",
            "ordinance_external_id",
            "member_id",
            "member_external_id",
            "member_name",
            "ward",
            "position",
        ]
    )
    for vm in rows:
        v = vm.vote
        meet = v.meeting if v else None
        ord_ = v.ordinance if v else None
        mem = vm.member
        w.writerow(
            [
                str(v.id) if v else "",
                v.external_id if v else "",
                str(v.meeting_id) if v else "",
                meet.external_id if meet else "",
                str(v.ordinance_id) if v else "",
                ord_.external_id if ord_ else "",
                str(vm.member_id),
                mem.external_id if mem else "",
                mem.name if mem else "",
                mem.ward if mem.ward is not None else "",
                vm.position.value,
            ]
        )
    return buf.getvalue().encode("utf-8")


def vote_members_json(rows: list[VoteMember]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for vm in rows:
        v = vm.vote
        meet = v.meeting if v else None
        ord_ = v.ordinance if v else None
        mem = vm.member
        items.append(
            {
                "vote_id": str(v.id) if v else None,
                "vote_external_id": v.external_id if v else None,
                "meeting_id": str(v.meeting_id) if v else None,
                "meeting_external_id": meet.external_id if meet else None,
                "ordinance_id": str(v.ordinance_id) if v else None,
                "ordinance_external_id": ord_.external_id if ord_ else None,
                "member_id": str(vm.member_id),
                "member_external_id": mem.external_id if mem else None,
                "member_name": mem.name if mem else None,
                "ward": mem.ward,
                "position": vm.position.value,
            }
        )
    return {"count": len(items), "items": items}
