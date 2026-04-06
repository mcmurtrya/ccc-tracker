"""Shared date and topic-tag parsing for API JSON ingest and CSV staging."""

from __future__ import annotations

from datetime import date
from typing import Any


def parse_iso_date_loose(value: Any) -> date | None:
    """Parse optional dates from API/JSON: ``None``, :class:`date`, or ISO ``YYYY-MM-DD`` string."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    raise TypeError(f"Expected date, str, or None, got {type(value)}")


def coerce_ward_optional(value: Any) -> int | None:
    """ELMS ``ward`` may be int or numeric string (e.g. ``\"11\"``)."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    s = str(value).strip()
    if s.isdigit():
        return int(s)
    return None


def parse_iso_date_field(value: str | None, field: str) -> tuple[date | None, str | None]:
    """Parse a non-empty CSV field as ``YYYY-MM-DD``. Returns ``(date, None)`` or ``(None, error)``."""
    if value is None or str(value).strip() == "":
        return None, f"{field} is required"
    raw = str(value).strip()[:10]
    try:
        return date.fromisoformat(raw), None
    except ValueError:
        return None, f"{field} must be YYYY-MM-DD, got {value!r}"


def parse_iso_date_optional_field(value: str | None, field: str) -> tuple[date | None, str | None]:
    """Parse optional CSV date: empty → ``(None, None)``; invalid → ``(None, error)``."""
    if value is None or str(value).strip() == "":
        return None, None
    raw = str(value).strip()[:10]
    try:
        return date.fromisoformat(raw), None
    except ValueError:
        return None, f"{field} must be YYYY-MM-DD, got {value!r}"


def parse_topic_tags(raw: str | None) -> list[str] | None:
    """Split tags on ``|``, ``;``, or ``,``; single token returns one-element list."""
    if raw is None or not str(raw).strip():
        return None
    text = str(raw).strip()
    for sep in ("|", ";", ","):
        if sep in text:
            parts = [p.strip() for p in text.split(sep)]
            out = [p for p in parts if p]
            return out or None
    return [text]


def coerce_topic_tags(value: Any) -> list[str] | None:
    """Normalize ``topic_tags`` from API JSON: ``None``, list of strings, or string (split like CSV)."""
    if value is None:
        return None
    if isinstance(value, list):
        out = [str(x).strip() for x in value if str(x).strip()]
        return out or None
    if isinstance(value, str):
        return parse_topic_tags(value)
    return None
