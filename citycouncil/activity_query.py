"""Shared parsing and limits for ``GET /activity`` and ``GET /feed.xml``."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from citycouncil.activity import (
    ActivityFeedResponse,
    default_since,
    fetch_activity,
    parse_activity_types,
    parse_iso8601_datetime,
)
from citycouncil.config import Settings
from citycouncil.search_limits import clamp_int


def _strip_activity_param(s: str | None) -> str | None:
    if s is None:
        return None
    t = s.strip()
    return t if t else None


def normalize_activity_q(raw: str | None, *, max_chars: int) -> str | None:
    """Strip whitespace; empty becomes ``None``; long values truncated to ``max_chars``."""
    s = _strip_activity_param(raw)
    if s is None:
        return None
    if len(s) > max_chars:
        return s[:max_chars]
    return s


def parse_activity_datetimes(
    settings: Settings,
    since: str | None,
    until: str | None,
) -> tuple[datetime, datetime | None]:
    """Return ``(since_dt, until_dt)``. Raises ``ValueError`` on bad input or range."""
    since_s = _strip_activity_param(since)
    until_s = _strip_activity_param(until)
    try:
        since_dt = parse_iso8601_datetime(since_s) if since_s else default_since(settings)
    except ValueError as e:
        raise ValueError(f"Invalid 'since' datetime: {e}") from e
    try:
        until_dt = parse_iso8601_datetime(until_s) if until_s else None
    except ValueError as e:
        raise ValueError(f"Invalid 'until' datetime: {e}") from e
    if until_dt is not None and until_dt < since_dt:
        raise ValueError("until must be >= since")
    return since_dt, until_dt


def resolve_activity_limit(settings: Settings, limit: int | None, *, rss: bool) -> int:
    lim = clamp_int(limit, default=settings.activity_default_limit, lo=1, hi=settings.activity_max_limit)
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
) -> ActivityFeedResponse:
    """Parse params and call :func:`~citycouncil.activity.fetch_activity`."""
    types_parsed = parse_activity_types(types)
    since_dt, until_dt = parse_activity_datetimes(settings, since, until)
    lim = resolve_activity_limit(settings, limit, rss=rss)
    off = 0 if rss else offset
    q = normalize_activity_q(filter_q, max_chars=settings.activity_q_max_chars)
    return await fetch_activity(
        session,
        since=since_dt,
        until=until_dt,
        types=types_parsed,
        limit=lim,
        offset=off,
        q=q,
    )
