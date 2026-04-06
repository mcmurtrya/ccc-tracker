import pytest

from citycouncil.activity_query import (
    normalize_activity_q,
    parse_activity_datetimes,
    resolve_activity_limit,
)
from citycouncil.config import Settings


def test_resolve_activity_limit_rss_caps_at_100() -> None:
    s = Settings()
    assert resolve_activity_limit(s, 500, rss=True) == 100


def test_parse_activity_datetimes_until_before_since() -> None:
    s = Settings()
    with pytest.raises(ValueError, match="until must be >= since"):
        parse_activity_datetimes(s, "2026-02-01T00:00:00Z", "2026-01-01T00:00:00Z")


def test_parse_activity_datetimes_whitespace_since_uses_default() -> None:
    s = Settings()
    since_dt, until_dt = parse_activity_datetimes(s, "   ", None)
    assert until_dt is None
    assert since_dt.tzinfo is not None


def test_parse_activity_datetimes_invalid_since_message() -> None:
    s = Settings()
    with pytest.raises(ValueError, match="Invalid 'since' datetime"):
        parse_activity_datetimes(s, "not-a-date", None)


def test_normalize_activity_q_truncates() -> None:
    s = Settings()
    long_q = "x" * (s.activity_q_max_chars + 50)
    out = normalize_activity_q(long_q, max_chars=s.activity_q_max_chars)
    assert out is not None
    assert len(out) == s.activity_q_max_chars
