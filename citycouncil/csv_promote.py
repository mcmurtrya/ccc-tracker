"""Promote accepted CSV staging rows into core `meetings` and `ordinances` (P2-301 follow-up)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from citycouncil.db.models import (
    CsvImportBatch,
    CsvImportStagingRow,
    CsvStagingRowStatus,
    Meeting,
    Ordinance,
    utc_now,
)
from citycouncil.parsing import coerce_topic_tags


def _parse_iso_date(value: Any) -> date | None:
    if value is None or str(value).strip() == "":
        return None
    return date.fromisoformat(str(value).strip()[:10])


async def upsert_meeting_from_csv_payload(session: AsyncSession, payload: dict[str, Any]) -> Meeting:
    ext = str(payload["meeting_id"])
    mdate = _parse_iso_date(payload.get("meeting_date"))
    if mdate is None:
        raise ValueError("meeting_date is required for promotion")
    q = await session.execute(select(Meeting).where(Meeting.external_id == ext))
    existing = q.scalar_one_or_none()
    core = {
        "meeting_date": mdate,
        "body": (payload.get("meeting_body") or "").strip() or None,
        "location": (payload.get("location") or "").strip() or None,
        "status": (payload.get("meeting_status") or "").strip() or None,
        "raw_json": payload,
    }
    if existing:
        for k, v in core.items():
            setattr(existing, k, v)
        await session.flush()
        return existing
    m = Meeting(external_id=ext, **core)
    session.add(m)
    await session.flush()
    return m


async def upsert_ordinance_from_csv_payload(session: AsyncSession, payload: dict[str, Any]) -> Ordinance:
    ext = str(payload["ordinance_id"])
    title = (payload.get("title") or "").strip()
    if not title:
        raise ValueError("title is required for promotion")
    intro = _parse_iso_date(payload.get("introduced_date"))
    tags = coerce_topic_tags(payload.get("topic_tags"))
    sponsor = (payload.get("sponsor_id") or "").strip() or None

    q = await session.execute(select(Ordinance).where(Ordinance.external_id == ext))
    existing = q.scalar_one_or_none()
    core = {
        "title": title,
        "sponsor_external_id": sponsor,
        "introduced_date": intro,
        "topic_tags": tags,
        "raw_json": payload,
    }
    if existing:
        for k, v in core.items():
            setattr(existing, k, v)
        await session.flush()
        return existing
    o = Ordinance(external_id=ext, **core)
    session.add(o)
    await session.flush()
    return o


@dataclass
class PromoteResult:
    promoted: int
    failed: list[dict[str, str]]


async def promote_accepted_staging(
    session: AsyncSession,
    batch_id: uuid.UUID | None = None,
) -> PromoteResult:
    """Upsert meetings and ordinances for accepted staging rows not yet promoted."""
    q = (
        select(CsvImportStagingRow)
        .where(
            CsvImportStagingRow.status == CsvStagingRowStatus.accepted,
            CsvImportStagingRow.promoted_at.is_(None),
        )
        .order_by(CsvImportStagingRow.batch_id, CsvImportStagingRow.row_number)
    )
    if batch_id is not None:
        q = q.where(CsvImportStagingRow.batch_id == batch_id)

    rows = (await session.execute(q)).scalars().all()
    failed: list[dict[str, str]] = []
    promoted = 0
    now = utc_now()

    for sr in rows:
        p = sr.payload
        try:
            await upsert_meeting_from_csv_payload(session, p)
            await upsert_ordinance_from_csv_payload(session, p)
            sr.promoted_at = now
            sr.promotion_error = None
            promoted += 1
        except Exception as e:
            sr.promotion_error = repr(e)[:8000]
            failed.append({"staging_row_id": str(sr.id), "error": repr(e)})

    await session.flush()
    return PromoteResult(promoted=promoted, failed=failed)


def _batch_filter(batch_id: uuid.UUID | None):
    if batch_id is None:
        return None
    return CsvImportStagingRow.batch_id == batch_id


async def reconciliation_report(
    session: AsyncSession,
    batch_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """P2-302: counts and orphan checks between staging and core tables."""
    bf = _batch_filter(batch_id)

    total_q = select(func.count()).select_from(CsvImportStagingRow)
    if bf is not None:
        total_q = total_q.where(bf)
    total = int(await session.scalar(total_q) or 0)

    by_status: dict[str, int] = {}
    for status in CsvStagingRowStatus:
        q = select(func.count()).select_from(CsvImportStagingRow).where(CsvImportStagingRow.status == status)
        if bf is not None:
            q = q.where(bf)
        by_status[status.value] = int(await session.scalar(q) or 0)

    acc_cond = [CsvImportStagingRow.status == CsvStagingRowStatus.accepted]
    if bf is not None:
        acc_cond.append(bf)

    accepted_total = int(
        await session.scalar(select(func.count()).select_from(CsvImportStagingRow).where(and_(*acc_cond))) or 0
    )
    promoted_n = int(
        await session.scalar(
            select(func.count())
            .select_from(CsvImportStagingRow)
            .where(and_(*acc_cond, CsvImportStagingRow.promoted_at.isnot(None)))
        )
        or 0
    )
    pending_n = int(
        await session.scalar(
            select(func.count())
            .select_from(CsvImportStagingRow)
            .where(
                and_(
                    *acc_cond,
                    CsvImportStagingRow.promoted_at.is_(None),
                    CsvImportStagingRow.promotion_error.is_(None),
                )
            )
        )
        or 0
    )
    promotion_failed_n = int(
        await session.scalar(
            select(func.count())
            .select_from(CsvImportStagingRow)
            .where(and_(*acc_cond, CsvImportStagingRow.promotion_error.isnot(None)))
        )
        or 0
    )

    meetings_n = int(await session.scalar(select(func.count()).select_from(Meeting)) or 0)
    ord_n = int(await session.scalar(select(func.count()).select_from(Ordinance)) or 0)

    # Orphans: promoted rows whose external ids are missing from core (should not happen if promote succeeded)
    orphan_meetings: list[str] = []
    orphan_ord: list[str] = []
    prom_sel = select(CsvImportStagingRow).where(
        and_(*acc_cond, CsvImportStagingRow.promoted_at.isnot(None))
    ).limit(5000)
    prom_rows = (await session.execute(prom_sel)).scalars().all()
    for sr in prom_rows:
        mid = str(sr.payload.get("meeting_id") or "")
        oid = str(sr.payload.get("ordinance_id") or "")
        if mid:
            m = await session.scalar(select(Meeting.id).where(Meeting.external_id == mid))
            if m is None:
                orphan_meetings.append(mid)
        if oid:
            o = await session.scalar(select(Ordinance.id).where(Ordinance.external_id == oid))
            if o is None:
                orphan_ord.append(oid)

    batch_info: dict[str, Any] | None = None
    if batch_id is not None:
        b = await session.get(CsvImportBatch, batch_id)
        if b:
            batch_info = {
                "id": str(b.id),
                "filename": b.filename,
                "file_sha256": b.file_sha256,
                "row_count": b.row_count,
                "accepted_count": b.accepted_count,
            }

    return {
        "batch_id": str(batch_id) if batch_id else None,
        "batch": batch_info,
        "staging": {
            "total_rows": total,
            "by_status": by_status,
            "accepted": {
                "total": accepted_total,
                "promoted_to_core": promoted_n,
                "pending_promotion": pending_n,
                "promotion_failed": promotion_failed_n,
            },
        },
        "core": {
            "meetings": meetings_n,
            "ordinances": ord_n,
        },
        "orphans_after_promotion": {
            "meeting_external_ids_missing": sorted(set(orphan_meetings)),
            "ordinance_external_ids_missing": sorted(set(orphan_ord)),
        },
    }


async def promote_standalone(batch_id: uuid.UUID | None = None) -> PromoteResult:
    from citycouncil.config import get_settings
    from citycouncil.db.session import standalone_session

    settings = get_settings()
    async with standalone_session(settings) as session:
        try:
            result = await promote_accepted_staging(session, batch_id=batch_id)
            await session.commit()
            return result
        except Exception:
            await session.rollback()
            raise


async def reconciliation_standalone(batch_id: uuid.UUID | None = None) -> dict[str, Any]:
    from citycouncil.config import get_settings
    from citycouncil.db.session import standalone_session

    settings = get_settings()
    async with standalone_session(settings) as session:
        return await reconciliation_report(session, batch_id=batch_id)
