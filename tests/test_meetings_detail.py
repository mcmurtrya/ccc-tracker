import uuid

from fastapi.testclient import TestClient


def test_meeting_detail_not_found(client: TestClient) -> None:
    r = client.get(f"/meetings/{uuid.uuid4()}")
    assert r.status_code == 404
    assert r.json()["detail"] == "Meeting not found"
