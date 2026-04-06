"""Shared parsing and limits for ``GET /activity`` and ``GET /feed.xml``."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from citycouncil.activity import default_since, fetch_activity, parse_activity_types, parse_iso8601_datetime
from citycouncil.config import Settings


def parse_activity_datetimes(
    settings: Settings,
    since: str | None,
    until: str | None,
) -> tuple[datetime, datetime | None]:
    """Return ``(since_dt, until_dt)``. Raises ``ValueError`` on bad input or range."""
    try:
        since_dt = parse_iso8601_datetime(since) if since else default_since(settings)
        until_dt = parse_iso8601_datetime(until) if until else None
    except ValueError as e:
        raise ValueError(f"Invalid ISO8601 datetime: {e}") from e
    if until_dt is not None and until_dt < since_dt:
        raise ValueError("until must be >= since")
    return since_dt, until_dt


def resolve_activity_limit(settings: Settings, limit: int | None, *, rss: bool) -> int:
    lim = settings.activity_default_limit if limit is None else limit
    lim = min(max(lim, 1), settings.activity_max_limit)
    if rss:
        lim = min(lim, 100)
    return lim


async def run_activity_feed(
    session: AsyncSession,
    settings: Settings,
    *,
    since: str | None,
    until: str | None,
    types: str | None,
    limit: int | None,
    offset: int,
    filter_q: str | None,
    rss: bool,
) -> dict[str, Any]:
    """Parse params and call :func:`~citycouncil.activity.fetch_activity`."""
    types_parsed = parse_activity_types(types)
    since_dt, until_dt = parse_activity_datetimes(settings, since, until)
    lim = resolve_activity_limit(settings, limit, rss=rss)
    off = 0 if rss else offset
    return await fetch_activity(
        session,
        since=since_dt,
        until=until_dt,
        types=types_parsed,
        limit=lim,
        offset=off,
        q=filter_q,
        q_max_scan=settings.activity_q_max_scan,
    )
