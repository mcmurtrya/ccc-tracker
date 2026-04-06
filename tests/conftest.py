"""Shared pytest fixtures (DRY across test modules)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from citycouncil.api import app


@pytest.fixture
def client() -> TestClient:
    """TestClient with server exceptions suppressed (matches prior tests)."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def admin_key() -> str:
    """Stable admin secret for tests that patch env themselves."""
    return "dev-admin-secret-key"


@pytest.fixture
def client_with_admin(monkeypatch: pytest.MonkeyPatch, admin_key: str) -> TestClient:
    """Client with CITYCOUNCIL_ADMIN_API_KEY set before requests."""
    monkeypatch.setenv("CITYCOUNCIL_ADMIN_API_KEY", admin_key)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
