from citycouncil.activity import item_matches_q


def test_item_matches_q_meeting() -> None:
    item = {
        "kind": "meeting",
        "id": "x",
        "activity_at": "2026-01-01T00:00:00+00:00",
        "meeting": {"body": "Zoning Committee", "location": "City Hall", "status": "x"},
    }
    assert item_matches_q(item, "zoning") is True
    assert item_matches_q(item, "nowhere") is False


def test_item_matches_q_ordinance() -> None:
    item = {
        "kind": "ordinance",
        "id": "x",
        "activity_at": "2026-01-01T00:00:00+00:00",
        "ordinance": {"external_id": "o", "title": "Affordable housing", "topic_tags": ["housing"]},
    }
    assert item_matches_q(item, "housing") is True
