import pytest
from fastapi.testclient import TestClient

from citycouncil.export_data import meetings_csv


def test_meetings_csv_empty_has_header() -> None:
    out = meetings_csv([])
    assert out.startswith(b"id,external_id,meeting_date")


def test_export_meetings_requires_auth(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    monkeypatch.setenv("CITYCOUNCIL_ADMIN_API_KEY", "dev-admin-secret-key")
    r = client.get("/admin/export/meetings")
    assert r.status_code == 401


def test_export_meetings_json_ok(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    monkeypatch.setenv("CITYCOUNCIL_ADMIN_API_KEY", "dev-admin-secret-key")
    r = client.get("/admin/export/meetings?fmt=json", headers={"X-Admin-Key": "dev-admin-secret-key"})
    assert r.status_code == 200
    data = r.json()
    assert "count" in data
    assert "items" in data


def test_export_meetings_csv_ok(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    monkeypatch.setenv("CITYCOUNCIL_ADMIN_API_KEY", "dev-admin-secret-key")
    r = client.get("/admin/export/meetings?fmt=csv", headers={"X-Admin-Key": "dev-admin-secret-key"})
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
