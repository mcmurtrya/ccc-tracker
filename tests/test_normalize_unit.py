from datetime import date

import pytest

from citycouncil.db.models import VotePosition
from citycouncil.ingest.normalize import _pos
from citycouncil.parsing import parse_iso_date_loose


def test_parse_date_iso() -> None:
    assert parse_iso_date_loose("2024-03-15") == date(2024, 3, 15)


def test_vote_position_mapping() -> None:
    assert _pos("aye") == VotePosition.aye
    assert _pos("nay") == VotePosition.nay
    assert _pos("YES") == VotePosition.aye


def test_vote_position_invalid() -> None:
    with pytest.raises(ValueError):
        _pos("maybe")
