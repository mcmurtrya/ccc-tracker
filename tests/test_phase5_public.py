import uuid

from fastapi.testclient import TestClient


def test_feed_xml_returns_rss(client: TestClient) -> None:
    r = client.get("/feed.xml")
    assert r.status_code == 200
    assert "rss" in r.headers.get("content-type", "").lower()
    assert b"<rss" in r.content


def test_ordinance_not_found(client: TestClient) -> None:
    r = client.get(f"/ordinances/{uuid.uuid4()}")
    assert r.status_code == 404
