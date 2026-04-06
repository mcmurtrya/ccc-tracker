import pytest

from citycouncil.activity_query import parse_activity_datetimes, resolve_activity_limit
from citycouncil.config import Settings


def test_resolve_activity_limit_rss_caps_at_100() -> None:
    s = Settings()
    assert resolve_activity_limit(s, 500, rss=True) == 100


def test_parse_activity_datetimes_until_before_since() -> None:
    s = Settings()
    with pytest.raises(ValueError, match="until must be >= since"):
        parse_activity_datetimes(s, "2026-02-01T00:00:00Z", "2026-01-01T00:00:00Z")
