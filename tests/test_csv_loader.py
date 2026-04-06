from citycouncil.csv_loader import validate_and_normalize_row
from citycouncil.parsing import parse_topic_tags


def test_parse_topic_tags_pipe() -> None:
    assert parse_topic_tags("a|b|c") == ["a", "b", "c"]


def test_parse_topic_tags_single() -> None:
    assert parse_topic_tags("housing") == ["housing"]


def test_validate_ok() -> None:
    row = {
        "ordinance_id": "o1",
        "meeting_id": "m1",
        "meeting_date": "2024-01-15",
        "title": "Test",
        "topic_tags": "a;b",
    }
    norm, errors = validate_and_normalize_row(row, 2)
    assert not errors
    assert norm["ordinance_id"] == "o1"
    assert norm["topic_tags"] == ["a", "b"]


def test_validate_unknown_column() -> None:
    row = {
        "ordinance_id": "o1",
        "meeting_id": "m1",
        "meeting_date": "2024-01-15",
        "title": "Test",
        "extra_col": "x",
    }
    _norm, errors = validate_and_normalize_row(row, 2)
    assert errors
    assert any("unknown columns" in e for e in errors)


def test_validate_bad_date() -> None:
    row = {
        "ordinance_id": "o1",
        "meeting_id": "m1",
        "meeting_date": "not-a-date",
        "title": "Test",
    }
    _norm, errors = validate_and_normalize_row(row, 2)
    assert errors
