"""Unified activity feed (meetings, ordinances, document artifacts) for reporters / residents."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text

from citycouncil.config import Settings
from citycouncil.db.models import DocumentArtifact, Meeting, Ordinance


def parse_iso8601_datetime(value: str) -> datetime:
    """Parse ISO8601; treat naive as UTC."""
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
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
    """Case-insensitive substring match on titles, tags, meeting text, document names."""
    qn = q.strip().lower()
    if not qn:
        return True
    kind = item["kind"]
    if kind == "meeting":
        m = item["meeting"]
        hay = f"{m.get('body') or ''} {m.get('location') or ''} {m.get('status') or ''}".lower()
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
        return qn in fn or qn in uri
    return True


async def _load_activity_items(
    session: AsyncSession,
    *,
    since: datetime,
    until: datetime | None,
    types: frozenset[str],
    fetch_limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], bool]:
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
        )
    if "ordinances" in types:
        branches.append(
            """
            SELECT 'ordinance'::text AS kind, id, updated_at AS activity_at
            FROM ordinances
            WHERE updated_at >= :since
            """
            + (" AND updated_at <= :until" if until is not None else "")
        )
    if "documents" in types:
        branches.append(
            """
            SELECT 'document'::text AS kind, id, created_at AS activity_at
            FROM document_artifacts
            WHERE created_at >= :since
            """
            + (" AND created_at <= :until" if until is not None else "")
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

    meetings_by_id: dict[UUID, Meeting] = {}
    if meeting_ids:
        qm = await session.execute(select(Meeting).where(Meeting.id.in_(meeting_ids)))
        for m in qm.scalars().all():
            meetings_by_id[m.id] = m

    ordinances_by_id: dict[UUID, Ordinance] = {}
    if ordinance_ids:
        qo = await session.execute(select(Ordinance).where(Ordinance.id.in_(ordinance_ids)))
        for o in qo.scalars().all():
            ordinances_by_id[o.id] = o

    documents_by_id: dict[UUID, DocumentArtifact] = {}
    if document_ids:
        qd = await session.execute(select(DocumentArtifact).where(DocumentArtifact.id.in_(document_ids)))
        for d in qd.scalars().all():
            documents_by_id[d.id] = d

    items: list[dict[str, Any]] = []
    for r in raw_rows:
        kind = r["kind"]
        eid: UUID = r["id"]
        at: datetime = r["activity_at"]
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        base = {
            "kind": kind,
            "id": str(eid),
            "activity_at": at.isoformat(),
        }
        if kind == "meeting":
            m = meetings_by_id.get(eid)
            if m is None:
                continue
            base["meeting"] = {
                "external_id": m.external_id,
                "meeting_date": m.meeting_date.isoformat(),
                "body": m.body,
                "location": m.location,
                "status": m.status,
            }
        elif kind == "ordinance":
            o = ordinances_by_id.get(eid)
            if o is None:
                continue
            base["ordinance"] = {
                "external_id": o.external_id,
                "title": o.title,
                "introduced_date": o.introduced_date.isoformat() if o.introduced_date else None,
                "topic_tags": o.topic_tags,
            }
        else:
            d = documents_by_id.get(eid)
            if d is None:
                continue
            base["document"] = {
                "file_name": d.file_name,
                "source_url": d.source_url,
                "uri": d.uri,
                "attachment_type": d.attachment_type,
                "parse_status": d.parse_status.value,
                "meeting_id": str(d.meeting_id) if d.meeting_id else None,
            }
        items.append(base)

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
    q_max_scan: int = 2000,
) -> dict[str, Any]:
    """Return merged rows by ``activity_at`` desc, then ``id`` desc.

    If ``q`` is set, results are filtered in memory (substring match). Pagination uses a scan cap
    of ``q_max_scan`` SQL rows before filtering; ``has_more`` is best-effort.
    """
    if q and q.strip():
        scan = min(q_max_scan, max(limit + offset + 50, 200))
        items, _has_sql = await _load_activity_items(
            session,
            since=since,
            until=until,
            types=types,
            fetch_limit=scan,
            offset=0,
        )
        filtered = [i for i in items if item_matches_q(i, q)]
        page = filtered[offset : offset + limit + 1]
        has_more = len(page) > limit
        page = page[:limit]
        next_offset = offset + limit if has_more else None
        return {
            "since": since.isoformat(),
            "until": until.isoformat() if until else None,
            "count": len(page),
            "items": page,
            "next_offset": next_offset,
            "has_more": has_more,
            "q": q.strip(),
        }

    fetch_limit = limit + 1
    items, has_more_raw = await _load_activity_items(
        session,
        since=since,
        until=until,
        types=types,
        fetch_limit=fetch_limit,
        offset=offset,
    )
    has_more = has_more_raw
    items = items[:limit]
    next_offset = offset + limit if has_more else None

    return {
        "since": since.isoformat(),
        "until": until.isoformat() if until else None,
        "count": len(items),
        "items": items,
        "next_offset": next_offset,
        "has_more": has_more,
    }


def default_since(settings: Settings) -> datetime:
    """UTC lower bound when client omits ``since``."""
    return datetime.now(timezone.utc) - timedelta(days=settings.activity_default_since_days)
