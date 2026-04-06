"""Public meeting detail payload (agenda, votes, documents) for residents / reporters."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from citycouncil.db.models import AgendaItem, DocumentArtifact, Meeting, Vote, VoteMember


async def fetch_meeting_detail(session: AsyncSession, meeting_id: UUID) -> dict[str, Any] | None:
    """Load one meeting with agenda, votes (incl. roll call), and linked documents."""
    q = await session.execute(
        select(Meeting)
        .where(Meeting.id == meeting_id)
        .options(
            selectinload(Meeting.agenda_items).selectinload(AgendaItem.ordinance),
            selectinload(Meeting.votes).selectinload(Vote.ordinance),
            selectinload(Meeting.votes).selectinload(Vote.vote_members).selectinload(VoteMember.member),
        )
    )
    m = q.scalar_one_or_none()
    if m is None:
        return None

    doc_q = await session.execute(
        select(DocumentArtifact)
        .where(DocumentArtifact.meeting_id == meeting_id)
        .order_by(DocumentArtifact.created_at.asc())
    )
    documents = list(doc_q.scalars().all())

    agenda_sorted = sorted(m.agenda_items, key=lambda x: x.sequence)
    votes_sorted = sorted(m.votes, key=lambda x: (x.created_at, x.id))

    return {
        "meeting": {
            "id": str(m.id),
            "external_id": m.external_id,
            "meeting_date": m.meeting_date.isoformat(),
            "body": m.body,
            "location": m.location,
            "status": m.status,
        },
        "agenda_items": [_agenda_item_payload(a) for a in agenda_sorted],
        "votes": [_vote_payload(v) for v in votes_sorted],
        "documents": [_document_payload(d) for d in documents],
    }


def _agenda_item_payload(a: AgendaItem) -> dict[str, Any]:
    ord_payload = None
    if a.ordinance_id and a.ordinance:
        o = a.ordinance
        ord_payload = {
            "id": str(o.id),
            "external_id": o.external_id,
            "title": o.title,
            "introduced_date": o.introduced_date.isoformat() if o.introduced_date else None,
            "topic_tags": o.topic_tags,
            "llm_summary": o.llm_summary,
            "llm_tags": o.llm_tags,
        }
    return {
        "id": str(a.id),
        "sequence": a.sequence,
        "raw_text": a.raw_text,
        "ordinance": ord_payload,
    }


def _vote_payload(v: Vote) -> dict[str, Any]:
    ord_payload = {
        "id": str(v.ordinance.id),
        "external_id": v.ordinance.external_id,
        "title": v.ordinance.title,
    }
    members_sorted = sorted(v.vote_members, key=lambda vm: vm.member.name.lower())
    roll: list[dict[str, Any]] = []
    for vm in members_sorted:
        roll.append(
            {
                "member_id": str(vm.member.id),
                "name": vm.member.name,
                "ward": vm.member.ward,
                "position": vm.position.value,
            }
        )
    return {
        "id": str(v.id),
        "external_id": v.external_id,
        "result": v.result,
        "ayes": v.ayes,
        "nays": v.nays,
        "abstentions": v.abstentions,
        "ordinance": ord_payload,
        "roll_call": roll,
    }


def _document_payload(d: DocumentArtifact) -> dict[str, Any]:
    return {
        "id": str(d.id),
        "file_name": d.file_name,
        "source_url": d.source_url,
        "uri": d.uri,
        "attachment_type": d.attachment_type,
        "parse_status": d.parse_status.value,
        "bytes_size": d.bytes_size,
        "needs_review": d.needs_review,
    }
