"""Unified activity feed (meetings, ordinances, document artifacts) for reporters / residents."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal, NotRequired, TypedDict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text

from citycouncil.config import Settings
from citycouncil.db.models import DocumentArtifact, Meeting, Ordinance

logger = logging.getLogger(__name__)

_DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ActivityMeetingPayload(TypedDict):
    external_id: str
    meeting_date: str
    body: str | None
    location: str | None
    status: str | None


class ActivityOrdinancePayload(TypedDict):
    external_id: str
    title: str
    introduced_date: str | None
    topic_tags: list[str] | None


class ActivityDocumentPayload(TypedDict):
    file_name: str | None
    source_url: str | None
    uri: str
    attachment_type: str | None
    parse_status: str
    meeting_id: str | None


class ActivityMeetingItem(TypedDict):
    kind: Literal["meeting"]
    id: str
    activity_at: str
    meeting: ActivityMeetingPayload


class ActivityOrdinanceItem(TypedDict):
    kind: Literal["ordinance"]
    id: str
    activity_at: str
    ordinance: ActivityOrdinancePayload


class ActivityDocumentItem(TypedDict):
    kind: Literal["document"]
    id: str
    activity_at: str
    document: ActivityDocumentPayload


ActivityItem = ActivityMeetingItem | ActivityOrdinanceItem | ActivityDocumentItem


class ActivityFeedResponse(TypedDict):
    since: str
    until: str | None
    count: int
    items: list[ActivityItem]
    next_offset: int | None
    has_more: bool
    q: NotRequired[str]


def parse_iso8601_datetime(value: str) -> datetime:
    """Parse ISO8601 or date-only ``YYYY-MM-DD`` (UTC midnight); treat naive datetimes as UTC."""
    s = value.strip()
    if not s:
        raise ValueError("empty string")
    if _DATE_ONLY.fullmatch(s):
        d = date.fromisoformat(s)
        return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError as e:
        raise ValueError(f"not a valid ISO8601 datetime: {e}") from e
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def parse_activity_types(raw: str | None) -> frozenset[str]:
    """Comma-separated: meetings, ordinances, documents (default: all)."""
    if not raw or not raw.strip():
        return frozenset({"meetings", "ordinances", "documents"})
    parts = {p.strip().lower() for p in raw.split(",") if p.strip()}
    allowed = {"meetings", "ordinances", "documents"}
    bad = parts - allowed
    if bad:
        raise ValueError(f"invalid types: {sorted(bad)} (allowed: {sorted(allowed)})")
    if not parts:
        return frozenset({"meetings", "ordinances", "documents"})
    return frozenset(parts)


def item_matches_q(item: dict[str, Any], q: str) -> bool:
    """Case-insensitive substring match; mirrors ``_load_activity_items`` ``q`` SQL predicates."""
    qn = q.strip().lower()
    if not qn:
        return True
    kind = item["kind"]
    if kind == "meeting":
        m = item["meeting"]
        parts = [
            m.get("body") or "",
            m.get("location") or "",
            m.get("status") or "",
            m.get("external_id") or "",
        ]
        hay = " ".join(parts).lower()
        return qn in hay
    if kind == "ordinance":
        o = item["ordinance"]
        title = (o.get("title") or "").lower()
        tags = ",".join(o.get("topic_tags") or []).lower()
        return qn in title or qn in tags
    if kind == "document":
        d = item["document"]
        fn = (d.get("file_name") or "").lower()
        uri = (d.get("uri") or "").lower()
        su = (d.get("source_url") or "").lower()
        return qn in fn or qn in uri or qn in su
    return True


def _q_predicate_meetings() -> str:
    return """
            AND (
                position(lower(:q) in lower(coalesce(body, ''))) > 0
                OR position(lower(:q) in lower(coalesce(location, ''))) > 0
                OR position(lower(:q) in lower(coalesce(status, ''))) > 0
                OR position(lower(:q) in lower(coalesce(external_id, ''))) > 0
            )
            """


def _q_predicate_ordinances() -> str:
    return """
            AND (
                position(lower(:q) in lower(coalesce(title, ''))) > 0
                OR EXISTS (
                    SELECT 1
                    FROM unnest(coalesce(topic_tags, ARRAY[]::text[])) AS t(tag)
                    WHERE position(lower(:q) in lower(t.tag)) > 0
                )
            )
            """


def _q_predicate_documents() -> str:
    return """
            AND (
                position(lower(:q) in lower(coalesce(file_name, ''))) > 0
                OR position(lower(:q) in lower(coalesce(uri, ''))) > 0
                OR position(lower(:q) in lower(coalesce(source_url, ''))) > 0
            )
            """


async def _load_activity_items(
    session: AsyncSession,
    *,
    since: datetime,
    until: datetime | None,
    types: frozenset[str],
    fetch_limit: int,
    offset: int,
    q: str | None = None,
) -> tuple[list[ActivityItem], bool]:
    """Return (items, has_more_raw) where has_more_raw means SQL returned more than fetch_limit rows."""
    branches: list[str] = []
    if "meetings" in types:
        branches.append(
            """
            SELECT 'meeting'::text AS kind, id, updated_at AS activity_at
            FROM meetings
            WHERE updated_at >= :since
            """
            + (" AND updated_at <= :until" if until is not None else "")
            + (_q_predicate_meetings() if q else "")
        )
    if "ordinances" in types:
        branches.append(
            """
            SELECT 'ordinance'::text AS kind, id, updated_at AS activity_at
            FROM ordinances
            WHERE updated_at >= :since
            """
            + (" AND updated_at <= :until" if until is not None else "")
            + (_q_predicate_ordinances() if q else "")
        )
    if "documents" in types:
        branches.append(
            """
            SELECT 'document'::text AS kind, id, created_at AS activity_at
            FROM document_artifacts
            WHERE created_at >= :since
            """
            + (" AND created_at <= :until" if until is not None else "")
            + (_q_predicate_documents() if q else "")
        )

    if not branches:
        return [], False

    union_sql = " UNION ALL ".join(f"({b})" for b in branches)
    sql = text(
        f"""
        SELECT kind, id, activity_at
        FROM (
            {union_sql}
        ) AS merged
        ORDER BY activity_at DESC, id DESC
        LIMIT :fetch_limit OFFSET :offset
        """
    )
    params: dict[str, Any] = {
        "since": since,
        "fetch_limit": fetch_limit,
        "offset": offset,
    }
    if until is not None:
        params["until"] = until
    if q:
        params["q"] = q

    result = await session.execute(sql, params)
    raw_rows = list(result.mappings().all())
    has_more_raw = len(raw_rows) == fetch_limit

    meeting_ids: list[UUID] = []
    ordinance_ids: list[UUID] = []
    document_ids: list[UUID] = []
    for r in raw_rows:
        kid = r["kind"]
        eid = r["id"]
        if kid == "meeting":
            meeting_ids.append(eid)
        elif kid == "ordinance":
            ordinance_ids.append(eid)
        else:
            document_ids.append(eid)

    async def fetch_meetings() -> dict[UUID, Meeting]:
        if not meeting_ids:
            return {}
        qm = await session.execute(select(Meeting).where(Meeting.id.in_(meeting_ids)))
        return {m.id: m for m in qm.scalars().all()}

    async def fetch_ordinances() -> dict[UUID, Ordinance]:
        if not ordinance_ids:
            return {}
        qo = await session.execute(select(Ordinance).where(Ordinance.id.in_(ordinance_ids)))
        return {o.id: o for o in qo.scalars().all()}

    async def fetch_documents() -> dict[UUID, DocumentArtifact]:
        if not document_ids:
            return {}
        qd = await session.execute(select(DocumentArtifact).where(DocumentArtifact.id.in_(document_ids)))
        return {d.id: d for d in qd.scalars().all()}

    meetings_by_id, ordinances_by_id, documents_by_id = await asyncio.gather(
        fetch_meetings(),
        fetch_ordinances(),
        fetch_documents(),
    )

    items: list[ActivityItem] = []
    for r in raw_rows:
        kind = r["kind"]
        eid: UUID = r["id"]
        at: datetime = r["activity_at"]
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        if kind == "meeting":
            m = meetings_by_id.get(eid)
            if m is None:
                logger.warning("activity feed: meeting row missing after merge query (id=%s)", eid)
                continue
            meeting_item: ActivityMeetingItem = {
                "kind": "meeting",
                "id": str(eid),
                "activity_at": at.isoformat(),
                "meeting": {
                    "external_id": m.external_id,
                    "meeting_date": m.meeting_date.isoformat(),
                    "body": m.body,
                    "location": m.location,
                    "status": m.status,
                },
            }
            items.append(meeting_item)
        elif kind == "ordinance":
            o = ordinances_by_id.get(eid)
            if o is None:
                logger.warning("activity feed: ordinance row missing after merge query (id=%s)", eid)
                continue
            ordinance_item: ActivityOrdinanceItem = {
                "kind": "ordinance",
                "id": str(eid),
                "activity_at": at.isoformat(),
                "ordinance": {
                    "external_id": o.external_id,
                    "title": o.title,
                    "introduced_date": o.introduced_date.isoformat() if o.introduced_date else None,
                    "topic_tags": o.topic_tags,
                },
            }
            items.append(ordinance_item)
        else:
            d = documents_by_id.get(eid)
            if d is None:
                logger.warning("activity feed: document row missing after merge query (id=%s)", eid)
                continue
            document_item: ActivityDocumentItem = {
                "kind": "document",
                "id": str(eid),
                "activity_at": at.isoformat(),
                "document": {
                    "file_name": d.file_name,
                    "source_url": d.source_url,
                    "uri": d.uri,
                    "attachment_type": d.attachment_type,
                    "parse_status": d.parse_status.value,
                    "meeting_id": str(d.meeting_id) if d.meeting_id else None,
                },
            }
            items.append(document_item)

    return items, has_more_raw


async def fetch_activity(
    session: AsyncSession,
    *,
    since: datetime,
    until: datetime | None,
    types: frozenset[str],
    limit: int,
    offset: int,
    q: str | None = None,
) -> ActivityFeedResponse:
    """Return merged rows by ``activity_at`` desc, then ``id`` desc.

    If ``q`` is set, substring matching is applied in SQL (case-insensitive) on the same fields
    as the JSON payload: meeting body/location/status/external_id; ordinance title and topic
    tags; document file name, URI, and source URL.
    """
    q_norm = (q.strip() or None) if q is not None else None

    fetch_limit = limit + 1
    items, has_more_raw = await _load_activity_items(
        session,
        since=since,
        until=until,
        types=types,
        fetch_limit=fetch_limit,
        offset=offset,
        q=q_norm,
    )
    has_more = has_more_raw
    page = items[:limit]
    next_offset = offset + limit if has_more else None

    out: ActivityFeedResponse = {
        "since": since.isoformat(),
        "until": until.isoformat() if until else None,
        "count": len(page),
        "items": page,
        "next_offset": next_offset,
        "has_more": has_more,
    }
    if q_norm is not None:
        out["q"] = q_norm
    return out


def default_since(settings: Settings) -> datetime:
    """UTC lower bound when client omits ``since``."""
    return datetime.now(timezone.utc) - timedelta(days=settings.activity_default_since_days)
