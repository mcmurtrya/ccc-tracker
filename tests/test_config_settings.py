"""Tests for :mod:`citycouncil.config` settings loading."""

from __future__ import annotations

from citycouncil.config import Settings, database_url_sync, get_settings


def test_get_settings_returns_settings_instance() -> None:
    s = get_settings()
    assert isinstance(s, Settings)


def test_settings_database_url_default() -> None:
    s = Settings()
    assert "postgresql" in s.database_url


def test_database_url_sync_rewrites_asyncpg() -> None:
    u = "postgresql+asyncpg://u:p@localhost/db"
    assert database_url_sync(u) == "postgresql+psycopg2://u:p@localhost/db"


def test_database_url_sync_passthrough_other_schemes() -> None:
    u = "postgresql://u:p@localhost/db"
    assert database_url_sync(u) is u
