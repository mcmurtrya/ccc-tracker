from datetime import date

import pytest

from citycouncil.parsing import (
    coerce_topic_tags,
    coerce_ward_optional,
    parse_iso_date_field,
    parse_iso_date_loose,
    parse_iso_date_optional_field,
)


def test_parse_iso_date_loose() -> None:
    assert parse_iso_date_loose(None) is None
    assert parse_iso_date_loose(date(2024, 1, 2)) == date(2024, 1, 2)
    assert parse_iso_date_loose("2024-05-01T00:00:00") == date(2024, 5, 1)


def test_parse_iso_date_loose_rejects_non_date_types() -> None:
    with pytest.raises(TypeError, match="Expected date"):
        parse_iso_date_loose(20240101)


def test_parse_iso_date_field_required() -> None:
    d, err = parse_iso_date_field("", "meeting_date")
    assert d is None and err and "required" in err
    d2, err2 = parse_iso_date_field("2024-06-01", "meeting_date")
    assert d2 == date(2024, 6, 1) and err2 is None


def test_parse_iso_date_optional_field() -> None:
    d, err = parse_iso_date_optional_field("", "introduced_date")
    assert d is None and err is None
    d2, err2 = parse_iso_date_optional_field("bad", "introduced_date")
    assert d2 is None and err2 and "YYYY-MM-DD" in err2


def test_coerce_topic_tags() -> None:
    assert coerce_topic_tags(None) is None
    assert coerce_topic_tags([" a ", "b"]) == ["a", "b"]
    assert coerce_topic_tags("x|y") == ["x", "y"]


def test_coerce_ward_optional_accepts_int_and_numeric_string() -> None:
    assert coerce_ward_optional(None) is None
    assert coerce_ward_optional(3) == 3
    assert coerce_ward_optional(" 12 ") == 12
    assert coerce_ward_optional("ward") is None


def test_coerce_topic_tags_non_string_sequence_returns_none() -> None:
    assert coerce_topic_tags(42) is None


def test_coerce_topic_tags_all_blank_strings_returns_none() -> None:
    assert coerce_topic_tags(["  ", ""]) is None
