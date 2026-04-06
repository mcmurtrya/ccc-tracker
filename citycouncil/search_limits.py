"""Search request limits (aligned with ``Settings.search_*``)."""

from __future__ import annotations

from citycouncil.config import Settings


def clamp_search_limit(settings: Settings, limit: int | None) -> int:
    """Apply default and cap at ``search_max_limit`` (lenient: no 422 for over-max)."""
    lim = settings.search_default_limit if limit is None else limit
    return min(max(lim, 1), settings.search_max_limit)
