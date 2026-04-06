from __future__ import annotations

import csv
import hashlib
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from citycouncil.db.models import (
    CsvImportBatch,
    CsvImportStagingRow,
    CsvStagingRowStatus,
    Ordinance,
    utc_now,
)
from citycouncil.parsing import (
    parse_iso_date_field,
    parse_iso_date_optional_field,
    parse_topic_tags,
)

# Canonical CSV headers (case-insensitive). P2-301: validate before staging.
REQUIRED_COLUMNS = frozenset(
    {
        "ordinance_id",
        "meeting_id",
        "meeting_date",
        "title",
    }
)

OPTIONAL_COLUMNS = frozenset(
    {
        "sponsor_id",
        "introduced_date",
        "topic_tags",
        "meeting_body",
        "location",
        "meeting_status",
    }
)

ALLOWED_COLUMNS = REQUIRED_COLUMNS | OPTIONAL_COLUMNS


def _norm_header(s: str) -> str:
    return (s or "").strip().lower()


def _strip_or_none(value: str | None) -> str | None:
    s = (value or "").strip()
    return s if s else None


def _make_staging_row(
    batch_id: uuid.UUID,
    row_number: int,
    dedupe_key: str,
    payload: dict[str, Any],
    status: CsvStagingRowStatus,
    errors: list[str] | None,
) -> dict[str, Any]:
    return {
        "id": uuid.uuid4(),
        "batch_id": batch_id,
        "row_number": row_number,
        "dedupe_key": dedupe_key,
        "payload": payload,
        "status": status,
        "errors": errors,
    }


def validate_and_normalize_row(
    row: dict[str, str],
    row_number: int,
) -> tuple[dict[str, Any], list[str]]:
    """Return normalized payload + validation errors (empty if OK)."""
    errors: list[str] = []
    norm: dict[str, Any] = {}

    ord_id = (row.get("ordinance_id") or "").strip()
    meet_id = (row.get("meeting_id") or "").strip()
    title = (row.get("title") or "").strip()

    if not ord_id:
        errors.append("ordinance_id is required")
    if not meet_id:
        errors.append("meeting_id is required")
    if not title:
        errors.append("title is required")

    md, err = parse_iso_date_field(row.get("meeting_date"), "meeting_date")
    if err:
        errors.append(err)
    elif md is None:
        errors.append("meeting_date is required")

    intro: date | None = None
    if row.get("introduced_date"):
        intro, ierr = parse_iso_date_optional_field(row.get("introduced_date"), "introduced_date")
        if ierr:
            errors.append(ierr)

    extra_keys = {_norm_header(k) for k in row.keys()} - ALLOWED_COLUMNS
    if extra_keys:
        errors.append(f"unknown columns: {sorted(extra_keys)}")

    norm.update(
        {
            "row_number": row_number,
            "ordinance_id": ord_id,
            "meeting_id": meet_id,
            "meeting_date": md.isoformat() if md else None,
            "title": title,
            "sponsor_id": _strip_or_none(row.get("sponsor_id")),
            "introduced_date": intro.isoformat() if intro else None,
            "topic_tags": parse_topic_tags(row.get("topic_tags")),
            "meeting_body": _strip_or_none(row.get("meeting_body")),
            "location": _strip_or_none(row.get("location")),
            "meeting_status": _strip_or_none(row.get("meeting_status")),
        }
    )
    return norm, errors


def _headers_ok(fieldnames: list[str] | None) -> tuple[bool, list[str]]:
    if not fieldnames:
        return False, ["CSV has no header row"]
    norm = {_norm_header(h) for h in fieldnames if h}
    missing = sorted(REQUIRED_COLUMNS - norm)
    if missing:
        return False, [f"missing required columns: {missing}"]
    return True, []


@dataclass
class CsvLoadResult:
    batch_id: str
    file_sha256: str
    row_count: int
    accepted_count: int
    duplicate_file_count: int
    duplicate_db_count: int
    invalid_count: int


async def load_csv_to_staging(session: AsyncSession, path: Path | str) -> CsvLoadResult:
    """Load a CSV file into staging: validate columns, dedupe (file + DB), bulk insert."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(str(p.resolve()))

    raw = p.read_bytes()
    file_sha256 = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8-sig")
    lines = text.splitlines()
    if not lines:
        raise ValueError("CSV is empty")

    reader = csv.DictReader(lines)
    header_ok, header_errors = _headers_ok(reader.fieldnames)
    if not header_ok:
        raise ValueError("; ".join(header_errors))

    rows_raw: list[dict[str, str]] = []
    for r in reader:
        rows_raw.append({_norm_header(k): (v or "") for k, v in r.items() if k is not None})

    ord_ids_in_file = [
        oid for r in rows_raw if (oid := (r.get("ordinance_id") or "").strip())
    ]

    existing_in_db: set[str] = set()
    if ord_ids_in_file:
        q = await session.execute(select(Ordinance.external_id).where(Ordinance.external_id.in_(ord_ids_in_file)))
        existing_in_db = set(q.scalars().all())

    seen_in_file: set[str] = set()
    staging_rows: list[dict[str, Any]] = []
    batch_id = uuid.uuid4()

    accepted = 0
    dup_file = 0
    dup_db = 0
    invalid = 0

    for i, raw_row in enumerate(rows_raw, start=2):
        norm, verrors = validate_and_normalize_row(raw_row, i)
        dedupe_key = (norm.get("ordinance_id") or "").strip() or f"row-{i}"

        if verrors:
            invalid += 1
            staging_rows.append(
                _make_staging_row(
                    batch_id,
                    i,
                    dedupe_key,
                    norm,
                    CsvStagingRowStatus.invalid,
                    verrors,
                )
            )
            continue

        oid = norm["ordinance_id"]
        if oid in seen_in_file:
            dup_file += 1
            staging_rows.append(
                _make_staging_row(
                    batch_id,
                    i,
                    dedupe_key,
                    norm,
                    CsvStagingRowStatus.duplicate_file,
                    ["duplicate ordinance_id earlier in this file"],
                )
            )
            continue

        if oid in existing_in_db:
            dup_db += 1
            staging_rows.append(
                _make_staging_row(
                    batch_id,
                    i,
                    dedupe_key,
                    norm,
                    CsvStagingRowStatus.duplicate_db,
                    ["ordinance_id already exists in ordinances table"],
                )
            )
            continue

        seen_in_file.add(oid)
        accepted += 1
        staging_rows.append(
            _make_staging_row(
                batch_id,
                i,
                dedupe_key,
                norm,
                CsvStagingRowStatus.accepted,
                None,
            )
        )

    now = utc_now()
    batch_row = {
        "id": batch_id,
        "filename": p.name,
        "file_sha256": file_sha256,
        "row_count": len(rows_raw),
        "accepted_count": accepted,
        "duplicate_file_count": dup_file,
        "duplicate_db_count": dup_db,
        "invalid_count": invalid,
        "notes": None,
        "created_at": now,
    }

    await session.execute(insert(CsvImportBatch).values(**batch_row))
    if staging_rows:
        for sr in staging_rows:
            sr["created_at"] = now
        await session.execute(insert(CsvImportStagingRow), staging_rows)

    return CsvLoadResult(
        batch_id=str(batch_id),
        file_sha256=file_sha256,
        row_count=len(rows_raw),
        accepted_count=accepted,
        duplicate_file_count=dup_file,
        duplicate_db_count=dup_db,
        invalid_count=invalid,
    )


async def load_csv_standalone(path: Path | str) -> CsvLoadResult:
    from citycouncil.config import get_settings
    from citycouncil.db.session import standalone_session

    settings = get_settings()
    async with standalone_session(settings) as session:
        try:
            result = await load_csv_to_staging(session, path)
            await session.commit()
            return result
        except Exception:
            await session.rollback()
            raise
