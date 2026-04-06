from datetime import date

from citycouncil.csv_promote import _parse_iso_date


def test_parse_iso_date() -> None:
    assert _parse_iso_date("2024-06-01") == date(2024, 6, 1)
    assert _parse_iso_date(None) is None
    assert _parse_iso_date("") is None
