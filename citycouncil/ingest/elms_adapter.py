"""Map Chicago eLMS HTTP JSON into the fixture-shaped payload expected by :mod:`normalize`."""

from __future__ import annotations

from typing import Any


def adapt_elms_poll_response(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize eLMS list JSON into a dict with a ``meetings`` list.

    The public API returns paged objects under ``data`` (see Swagger). Older demos and
    tests may already use a ``meetings`` array; those pass through unchanged.
    """
    if isinstance(payload.get("meetings"), list):
        return payload

    rows: list[Any] | None = payload.get("data")  # type: ignore[assignment]
    if rows is None and isinstance(payload.get("value"), list):
        rows = payload["value"]
    if not isinstance(rows, list):
        raise ValueError(
            "ELMS poll response must include a 'meetings' list or a list under 'data' (or OData 'value')"
        )

    return {"meetings": [_elms_meeting_row_to_bundle(r) for r in rows]}


def _elms_meeting_row_to_bundle(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise TypeError(f"Expected meeting object dict, got {type(row)}")
    mid = row.get("meetingId")
    if not mid:
        raise ValueError("ELMS meeting row missing meetingId")
    return {
        "id": str(mid),
        "date": row.get("date"),
        "body": row.get("body"),
        "location": row.get("location"),
        "status": row.get("status"),
        "members": [],
        "ordinances": [],
        "agenda_items": [],
        "votes": [],
        "elms": row,
    }
