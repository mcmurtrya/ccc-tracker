from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from citycouncil.db.models import (
    AgendaItem,
    Meeting,
    Member,
    Ordinance,
    Vote,
    VoteMember,
    VotePosition,
)
from citycouncil.parsing import coerce_topic_tags, coerce_ward_optional, parse_iso_date_loose


def _pos(raw: str) -> VotePosition:
    key = str(raw).lower().strip()
    mapping = {
        "aye": VotePosition.aye,
        "yes": VotePosition.aye,
        "y": VotePosition.aye,
        "nay": VotePosition.nay,
        "no": VotePosition.nay,
        "n": VotePosition.nay,
        "abstain": VotePosition.abstain,
        "absent": VotePosition.absent,
    }
    if key not in mapping:
        raise ValueError(f"Unknown vote position: {raw!r}")
    return mapping[key]


async def _upsert_by_external_id(
    session: AsyncSession,
    model: type[Member] | type[Ordinance] | type[Meeting],
    external_id: str,
    payload: dict[str, Any],
) -> Member | Ordinance | Meeting:
    q = await session.execute(select(model).where(model.external_id == external_id))
    existing = q.scalar_one_or_none()
    if existing:
        for k, v in payload.items():
            setattr(existing, k, v)
        await session.flush()
        return existing
    inst = model(external_id=external_id, **payload)
    session.add(inst)
    await session.flush()
    return inst


async def _upsert_member(session: AsyncSession, row: dict[str, Any]) -> Member:
    ext = str(row["id"])
    payload = {
        "name": str(row.get("name") or ext),
        "ward": coerce_ward_optional(row.get("ward")),
        "body": row.get("body"),
        "term_start": parse_iso_date_loose(row.get("term_start")),
        "term_end": parse_iso_date_loose(row.get("term_end")),
        "raw_json": row,
    }
    out = await _upsert_by_external_id(session, Member, ext, payload)
    assert isinstance(out, Member)
    return out


async def _upsert_ordinance(session: AsyncSession, row: dict[str, Any]) -> Ordinance:
    ext = str(row["id"])
    payload = {
        "title": str(row.get("title") or ext),
        "sponsor_external_id": str(row["sponsor_id"]) if row.get("sponsor_id") else None,
        "introduced_date": parse_iso_date_loose(row.get("introduced_date")),
        "topic_tags": coerce_topic_tags(row.get("topic_tags")),
        "raw_json": row,
    }
    out = await _upsert_by_external_id(session, Ordinance, ext, payload)
    assert isinstance(out, Ordinance)
    return out


async def _upsert_meeting(session: AsyncSession, row: dict[str, Any]) -> Meeting:
    ext = str(row["id"])
    payload = {
        "meeting_date": parse_iso_date_loose(row["date"]),
        "body": row.get("body"),
        "location": row.get("location"),
        "status": row.get("status"),
        "raw_json": row,
    }
    out = await _upsert_by_external_id(session, Meeting, ext, payload)
    assert isinstance(out, Meeting)
    return out


async def ingest_meeting_bundle(session: AsyncSession, bundle: dict[str, Any]) -> Meeting:
    """Normalize and persist one meeting object (members, ordinances, agenda, votes)."""
    member_by_ext: dict[str, Member] = {}
    for m in bundle.get("members") or []:
        mem = await _upsert_member(session, m)
        member_by_ext[str(m["id"])] = mem

    ord_by_ext: dict[str, Ordinance] = {}
    for o in bundle.get("ordinances") or []:
        ordn = await _upsert_ordinance(session, o)
        ord_by_ext[str(o["id"])] = ordn

    meeting = await _upsert_meeting(session, bundle)

    await session.execute(delete(AgendaItem).where(AgendaItem.meeting_id == meeting.id))
    await session.execute(delete(Vote).where(Vote.meeting_id == meeting.id))
    await session.flush()

    for item in bundle.get("agenda_items") or []:
        seq = int(item["sequence"])
        oid = item.get("ordinance_id")
        ordn_uuid: UUID | None = None
        if oid is not None:
            o = ord_by_ext.get(str(oid))
            if o is None:
                raise ValueError(f"Agenda item references unknown ordinance_id={oid!r}")
            ordn_uuid = o.id
        session.add(
            AgendaItem(
                meeting_id=meeting.id,
                ordinance_id=ordn_uuid,
                sequence=seq,
                raw_text=item.get("raw_text"),
                raw_json=item,
            )
        )

    for idx, v in enumerate(bundle.get("votes") or []):
        oid = v.get("ordinance_id")
        if oid is None:
            raise ValueError("vote missing ordinance_id")
        ordn = ord_by_ext.get(str(oid))
        if ordn is None:
            raise ValueError(f"vote references unknown ordinance_id={oid!r}")
        vote_ext = v.get("id") or f"synth-{meeting.external_id}-{ordn.external_id}-{idx}"
        vote = Vote(
            external_id=str(vote_ext),
            ordinance_id=ordn.id,
            meeting_id=meeting.id,
            result=v.get("result"),
            ayes=v.get("ayes"),
            nays=v.get("nays"),
            abstentions=v.get("abstentions"),
            raw_json=v,
        )
        session.add(vote)
        await session.flush()

        for vm in v.get("members") or []:
            mid = str(vm["member_id"])
            mem = member_by_ext.get(mid)
            if mem is None:
                q = await session.execute(select(Member).where(Member.external_id == mid))
                mem = q.scalar_one_or_none()
            if mem is None:
                raise ValueError(f"vote member references unknown member_id={mid!r}")
            session.add(
                VoteMember(
                    vote_id=vote.id,
                    member_id=mem.id,
                    position=_pos(str(vm.get("position") or "absent")),
                )
            )

    await session.flush()
    return meeting


async def ingest_payload(session: AsyncSession, payload: dict[str, Any]) -> list[UUID]:
    """Ingest full API response: expects {\"meetings\": [ ... ] }."""
    meetings = payload.get("meetings")
    if not isinstance(meetings, list):
        raise ValueError("payload must contain a list 'meetings'")
    ids: list[UUID] = []
    for m in meetings:
        meeting = await ingest_meeting_bundle(session, m)
        ids.append(meeting.id)
    return ids
