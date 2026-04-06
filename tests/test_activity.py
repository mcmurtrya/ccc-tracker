from datetime import timezone

import pytest
from fastapi.testclient import TestClient

from citycouncil.activity import parse_activity_types, parse_iso8601_datetime


def test_parse_iso8601_z_suffix() -> None:
    dt = parse_iso8601_datetime("2025-01-01T12:00:00Z")
    assert dt.year == 2025
    assert dt.hour == 12


def test_parse_iso8601_offset() -> None:
    dt = parse_iso8601_datetime("2025-06-01T00:00:00+05:00")
    assert dt.utcoffset() is not None


def test_parse_iso8601_date_only_utc_midnight() -> None:
    dt = parse_iso8601_datetime("2025-03-15")
    assert dt.year == 2025 and dt.month == 3 and dt.day == 15
    assert dt.tzinfo == timezone.utc


def test_parse_iso8601_empty_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        parse_iso8601_datetime("   ")


def test_parse_activity_types_default_all() -> None:
    assert parse_activity_types(None) == frozenset({"meetings", "ordinances", "documents"})


def test_parse_activity_types_subset() -> None:
    assert parse_activity_types("meetings, ordinances") == frozenset({"meetings", "ordinances"})


def test_parse_activity_types_invalid() -> None:
    with pytest.raises(ValueError, match="invalid"):
        parse_activity_types("meetings,votes")


def test_activity_bad_since(client: TestClient) -> None:
    r = client.get("/activity?since=not-a-date")
    assert r.status_code == 400


def test_activity_until_before_since(client: TestClient) -> None:
    r = client.get(
        "/activity?since=2026-01-10T00:00:00Z&until=2026-01-01T00:00:00Z",
    )
    assert r.status_code == 400


def test_activity_default_ok(client: TestClient) -> None:
    r = client.get("/activity")
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "since" in data
    assert "has_more" in data
    assert isinstance(data["items"], list)
