"""Enums used by ORM models (Postgres ENUM types)."""

from __future__ import annotations

import enum


class VotePosition(str, enum.Enum):
    aye = "aye"
    nay = "nay"
    abstain = "abstain"
    absent = "absent"


class ParseStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    ok = "ok"
    failed = "failed"


class CsvStagingRowStatus(str, enum.Enum):
    """P2-301 staging row outcome."""

    accepted = "accepted"
    duplicate_file = "duplicate_file"
    duplicate_db = "duplicate_db"
    invalid = "invalid"
