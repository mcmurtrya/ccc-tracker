from citycouncil.rss import (
    _item_description,
    _item_link,
    _item_title,
    _pub_date,
    render_activity_rss,
)


def test_render_activity_rss_minimal() -> None:
    items = [
        {
            "kind": "meeting",
            "id": "00000000-0000-0000-0000-000000000001",
            "activity_at": "2026-01-15T12:00:00+00:00",
            "meeting": {
                "external_id": "m1",
                "meeting_date": "2026-01-15",
                "body": "Committee",
                "location": "Hall",
                "status": "Scheduled",
            },
        }
    ]
    xml = render_activity_rss(
        items,
        feed_title="t",
        feed_link="http://localhost:8000",
        feed_description="d",
        self_link="http://localhost:8000/feed.xml",
        base_url="http://localhost:8000",
    )
    assert "<?xml" in xml
    assert "<rss" in xml
    assert "Committee" in xml
    assert "http://localhost:8000/meetings/00000000-0000-0000-0000-000000000001" in xml


def test_render_activity_rss_ordinance_and_document() -> None:
    items = [
        {
            "kind": "ordinance",
            "id": "00000000-0000-0000-0000-000000000002",
            "activity_at": "2026-01-15T12:00:00+00:00",
            "ordinance": {"external_id": "o1", "title": "Zoning text", "topic_tags": ["zoning"]},
        },
        {
            "kind": "document",
            "id": "00000000-0000-0000-0000-000000000003",
            "activity_at": "2026-01-16T12:00:00+00:00",
            "document": {
                "file_name": "agenda.pdf",
                "source_url": "https://example.com/a.pdf",
                "uri": "https://example.com/b.pdf",
                "parse_status": "ok",
            },
        },
    ]
    xml = render_activity_rss(
        items,
        feed_title="feed",
        feed_link="http://localhost:8000",
        feed_description="d",
        self_link="http://localhost:8000/feed.xml",
        base_url="http://localhost:8000",
    )
    assert "Zoning text" in xml
    assert "/ordinances/00000000-0000-0000-0000-000000000002" in xml
    assert "https://example.com/a.pdf" in xml


def test_render_activity_rss_document_falls_back_to_uri() -> None:
    items = [
        {
            "kind": "document",
            "id": "00000000-0000-0000-0000-000000000004",
            "activity_at": "2026-01-15T12:00:00+00:00",
            "document": {
                "file_name": "x.pdf",
                "source_url": None,
                "uri": "https://blob.example/x.pdf",
                "parse_status": "pending",
            },
        },
    ]
    xml = render_activity_rss(
        items,
        feed_title="f",
        feed_link="http://localhost:8000",
        feed_description="d",
        self_link="http://localhost:8000/feed.xml",
        base_url="http://localhost:8000",
    )
    assert "https://blob.example/x.pdf" in xml


def test_pub_date_adds_utc_for_naive_iso() -> None:
    out = _pub_date("2026-06-01T10:00:00")
    assert "GMT" in out or "UTC" in out


def test_item_title_meeting_defaults_body() -> None:
    t = _item_title(
        {
            "kind": "meeting",
            "meeting": {"meeting_date": "2026-01-01", "body": None},
        }
    )
    assert "Meeting" in t


def test_item_title_document_defaults_file_name() -> None:
    assert (
        _item_title({"kind": "document", "document": {"file_name": None}})
        == "Document"
    )


def test_item_title_unknown_kind() -> None:
    assert _item_title({"kind": "custom"}) == "custom"


def test_item_link_document_missing_subdict_uses_base() -> None:
    assert (
        _item_link({"kind": "document", "id": "x", "document": None}, "http://h/")
        == "http://h"
    )


def test_item_link_unknown_kind_returns_base() -> None:
    assert _item_link({"kind": "other", "id": "1"}, "http://x/y/") == "http://x/y"


def test_item_description_unknown_kind_empty() -> None:
    assert _item_description({"kind": "unknown"}) == ""


def test_item_description_ordinance_skips_tags_when_empty() -> None:
    out = _item_description(
        {
            "kind": "ordinance",
            "ordinance": {"title": "Bare", "topic_tags": []},
        }
    )
    assert out == "Bare"
    assert "Tags" not in out
