"""Download ELMS meeting ``files[]`` into :class:`~citycouncil.db.models.DocumentArtifact` rows."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any, TypedDict

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from citycouncil.config import Settings, get_settings
from citycouncil.db.models import DocumentArtifact, Meeting, ParseStatus
from citycouncil.db.session import standalone_session
from citycouncil.ingest.http_download import download_bytes_limited

logger = logging.getLogger(__name__)


def extract_elms_files_from_meeting_raw_json(raw_json: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Return ELMS ``files`` entries from meeting ``raw_json`` (list or enriched bundle)."""
    if not raw_json or not isinstance(raw_json, dict):
        return []
    elms = raw_json.get("elms")
    files: list[Any] | None = None
    if isinstance(elms, dict):
        f = elms.get("files")
        if isinstance(f, list):
            files = f
    if files is None and isinstance(raw_json.get("files"), list):
        files = raw_json["files"]
    if not files:
        return []
    return [x for x in files if isinstance(x, dict)]


def _is_pdf_candidate(url: str, file_name: str | None) -> bool:
    u = url.lower()
    if u.endswith(".pdf"):
        return True
    fn = (file_name or "").lower()
    return fn.endswith(".pdf")


class DocumentsSyncTotals(TypedDict):
    """Return value of :func:`sync_documents_standalone`."""

    meetings: int
    downloaded: int
    skipped: int
    errors: int
    meeting_ids: list[str]


async def sync_meeting_documents(
    session: AsyncSession,
    client: httpx.AsyncClient,
    settings: Settings,
    meeting: Meeting,
) -> dict[str, int]:
    """Download PDF files for one meeting; insert :class:`DocumentArtifact` rows (deduped)."""
    files = extract_elms_files_from_meeting_raw_json(meeting.raw_json)
    downloaded = 0
    skipped = 0
    errors = 0

    for meta in files:
        url = meta.get("path") or meta.get("url")
        if not url or not isinstance(url, str):
            errors += 1
            continue
        fn = meta.get("fileName") if isinstance(meta.get("fileName"), str) else None
        at = meta.get("attachmentType") if isinstance(meta.get("attachmentType"), str) else None
        if settings.documents_sync_pdf_only and not _is_pdf_candidate(url, fn):
            skipped += 1
            continue

        q = await session.execute(
            select(DocumentArtifact).where(
                DocumentArtifact.meeting_id == meeting.id,
                DocumentArtifact.source_url == url,
            )
        )
        if q.scalar_one_or_none() is not None:
            skipped += 1
            continue

        try:
            data = await download_bytes_limited(client, url, settings.documents_max_bytes)
        except Exception as e:
            logger.warning("download failed %s: %s", url, e)
            errors += 1
            continue

        digest = hashlib.sha256(data).hexdigest()
        local_path: str | None = None
        if settings.documents_local_dir:
            base = Path(settings.documents_local_dir).expanduser().resolve()
            base.mkdir(parents=True, exist_ok=True)
            fp = base / f"{digest}.pdf"
            fp.write_bytes(data)
            local_path = str(fp)
        doc = DocumentArtifact(
            meeting_id=meeting.id,
            sha256=digest,
            uri=url,
            source_url=url,
            file_name=fn,
            attachment_type=at,
            bytes_size=len(data),
            raw_json=meta,
            parse_status=ParseStatus.pending,
            local_path=local_path,
        )
        session.add(doc)
        downloaded += 1

    await session.flush()
    return {"downloaded": downloaded, "skipped": skipped, "errors": errors}


async def sync_documents_standalone(
    settings: Settings | None = None,
    meeting_external_id: str | None = None,
) -> DocumentsSyncTotals:
    settings = settings or get_settings()
    totals: DocumentsSyncTotals = {
        "meetings": 0,
        "downloaded": 0,
        "skipped": 0,
        "errors": 0,
        "meeting_ids": [],
    }
    async with standalone_session(settings) as session:
        if meeting_external_id:
            q = await session.execute(
                select(Meeting).where(Meeting.external_id == meeting_external_id)
            )
            meetings = list(q.scalars().all())
        else:
            q = await session.execute(
                select(Meeting)
                .order_by(Meeting.meeting_date.desc())
                .limit(settings.documents_sync_max_meetings)
            )
            meetings = list(q.scalars().all())

        async with httpx.AsyncClient(timeout=settings.documents_http_timeout) as client:
            for m in meetings:
                st = await sync_meeting_documents(session, client, settings, m)
                totals["meetings"] += 1
                totals["downloaded"] += st["downloaded"]
                totals["skipped"] += st["skipped"]
                totals["errors"] += st["errors"]
                totals["meeting_ids"].append(str(m.id))
        await session.commit()
    return totals
