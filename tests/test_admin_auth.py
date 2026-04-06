import pytest
from fastapi.testclient import TestClient


def test_admin_returns_503_when_key_not_configured(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    # Override any value from `.env` (delenv alone does not block pydantic-settings reading `.env`).
    monkeypatch.setenv("CITYCOUNCIL_ADMIN_API_KEY", "")
    r = client.get("/admin/dlq")
    assert r.status_code == 503
    assert "disabled" in r.json()["detail"].lower()


def test_admin_requires_key_when_configured(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    monkeypatch.setenv("CITYCOUNCIL_ADMIN_API_KEY", "dev-admin-secret-key")
    assert client.get("/admin/dlq").status_code == 401
    assert client.get("/admin/dlq", headers={"X-Admin-Key": "wrong"}).status_code == 401


def test_admin_accepts_bearer_token(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    monkeypatch.setenv("CITYCOUNCIL_ADMIN_API_KEY", "dev-admin-secret-key")
    r = client.get(
        "/admin/dlq",
        headers={"Authorization": "Bearer dev-admin-secret-key"},
    )
    # Auth passes; response may be 200 or 5xx if Postgres is unavailable.
    assert r.status_code not in (401, 503)


def test_health_unauthenticated(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
