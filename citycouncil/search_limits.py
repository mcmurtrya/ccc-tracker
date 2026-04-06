"""Search request limits (aligned with ``Settings.search_*``)."""

from __future__ import annotations

from citycouncil.config import Settings


def clamp_int(value: int | None, *, default: int, lo: int, hi: int) -> int:
    """Use ``default`` when ``value`` is ``None``; clamp to ``[lo, hi]``."""
    v = default if value is None else value
    return min(max(v, lo), hi)


def clamp_search_limit(settings: Settings, limit: int | None) -> int:
    """Apply default and cap at ``search_max_limit`` (lenient: no 422 for over-max)."""
    return clamp_int(limit, default=settings.search_default_limit, lo=1, hi=settings.search_max_limit)
