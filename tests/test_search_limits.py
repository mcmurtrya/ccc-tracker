from citycouncil.config import Settings
from citycouncil.search_limits import clamp_int, clamp_search_limit


def test_clamp_search_limit_default() -> None:
    s = Settings()
    assert clamp_search_limit(s, None) == s.search_default_limit


def test_clamp_search_limit_caps_at_max() -> None:
    s = Settings()
    assert clamp_search_limit(s, 10_000) == s.search_max_limit


def test_clamp_search_limit_minimum_one() -> None:
    s = Settings()
    assert clamp_search_limit(s, 0) == 1


def test_clamp_int_uses_default_and_bounds() -> None:
    assert clamp_int(None, default=10, lo=1, hi=20) == 10
    assert clamp_int(0, default=10, lo=1, hi=20) == 1
    assert clamp_int(99, default=10, lo=1, hi=20) == 20
