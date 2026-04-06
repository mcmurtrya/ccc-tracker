"""Download PDF bytes and populate :class:`~citycouncil.db.models.DocumentChunk` rows."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, TypedDict
from uuid import UUID

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from citycouncil.config import Settings, get_settings
from citycouncil.db.models import DocumentArtifact, DocumentChunk, ParseStatus
from citycouncil.db.session import standalone_session
from citycouncil.ingest.http_download import download_bytes_limited
from citycouncil.ingest.pdf_ocr import extract_pdf_ocr_chunks
from citycouncil.ingest.pdf_text import extract_pdf_chunks, scan_pdf_metadata

logger = logging.getLogger(__name__)

_ALLOWED_STATUS = frozenset({"pending", "failed", "pending_or_failed", "all"})


class ExtractDocumentsStandaloneResult(TypedDict):
    """Return value of :func:`extract_documents_standalone`."""

    processed: int
    ok: int
    failed: int
    total_chunks: int
    needs_review_marked: int
    artifact_ids: list[str]
    status_filter: str


def _load_bytes_from_local(artifact: DocumentArtifact, settings: Settings) -> bytes | None:
    if not artifact.local_path:
        return None
    p = Path(artifact.local_path)
    if not p.is_file():
        return None
    data = p.read_bytes()
    if len(data) > settings.documents_max_bytes:
        raise ValueError("local file exceeds documents_max_bytes")
    return data


def _apply_extract_status_filter(stmt: Any, status_filter: str) -> Any:
    if status_filter == "all":
        return stmt
    if status_filter == "pending":
        return stmt.where(DocumentArtifact.parse_status == ParseStatus.pending)
    if status_filter == "failed":
        return stmt.where(DocumentArtifact.parse_status == ParseStatus.failed)
    if status_filter == "pending_or_failed":
        return stmt.where(
            DocumentArtifact.parse_status.in_([ParseStatus.pending, ParseStatus.failed])
        )
    raise ValueError(f"invalid status filter: {status_filter!r}")


async def extract_one_artifact(
    session: AsyncSession,
    client: httpx.AsyncClient,
    settings: Settings,
    artifact: DocumentArtifact,
) -> dict[str, Any]:
    """Load PDF bytes (local disk or HTTP), extract text, replace chunks."""
    url = artifact.source_url or artifact.uri
    artifact.parse_status = ParseStatus.processing
    artifact.parse_error = None
    await session.flush()

    try:
        data = _load_bytes_from_local(artifact, settings)
        if data is None:
            if not url:
                artifact.parse_status = ParseStatus.failed
                artifact.parse_error = "no source_url or uri or readable local_path"
                await session.flush()
                return {
                    "status": "failed",
                    "chunks": 0,
                    "error": artifact.parse_error,
                    "needs_review": False,
                }
            data = await download_bytes_limited(client, url, settings.documents_max_bytes)
        chunk_rows = extract_pdf_chunks(data, settings.extract_max_chars_per_chunk)
        meta = scan_pdf_metadata(data)
        used_ocr = False
        if not chunk_rows and settings.extract_ocr_enabled:
            try:
                chunk_rows = extract_pdf_ocr_chunks(
                    data,
                    settings.extract_max_chars_per_chunk,
                    settings.extract_ocr_dpi,
                )
                used_ocr = bool(chunk_rows)
            except Exception as ocr_e:
                logger.warning("OCR fallback failed %s: %s", artifact.id, ocr_e)
    except Exception as e:
        logger.warning("extract failed %s: %s", artifact.id, e)
        artifact.parse_status = ParseStatus.failed
        artifact.parse_error = repr(e)[:8000]
        await session.flush()
        return {"status": "failed", "chunks": 0, "error": artifact.parse_error, "needs_review": False}

    await session.execute(
        delete(DocumentChunk).where(DocumentChunk.document_artifact_id == artifact.id)
    )

    meeting_id = artifact.meeting_id
    if not chunk_rows:
        # TXT-103: blank or scanned PDF — flag for OCR / manual follow-up (TXT-104).
        artifact.parse_status = ParseStatus.ok
        artifact.parse_error = "no_text_extracted"
        artifact.needs_review = True
        rj = artifact.raw_json
        if isinstance(rj, dict):
            artifact.raw_json = {**rj, "pdf_scan_meta": meta}
        else:
            artifact.raw_json = {"pdf_scan_meta": meta}
        await session.flush()
        return {
            "status": "ok",
            "chunks": 0,
            "error": None,
            "needs_review": True,
            "pdf_scan_meta": meta,
        }

    extractor_version = "pymupdf+tesseract" if used_ocr else "pymupdf"
    for idx, (page_num, body) in enumerate(chunk_rows):
        session.add(
            DocumentChunk(
                document_artifact_id=artifact.id,
                meeting_id=meeting_id,
                chunk_index=idx,
                page_number=page_num,
                body=body,
                extractor_version=extractor_version,
            )
        )

    artifact.parse_status = ParseStatus.ok
    artifact.parse_error = None
    artifact.needs_review = False
    await session.flush()
    return {
        "status": "ok",
        "chunks": len(chunk_rows),
        "error": None,
        "needs_review": False,
        "pdf_scan_meta": meta,
        "ocr_used": used_ocr,
    }


async def extract_documents_standalone(
    settings: Settings | None = None,
    *,
    limit: int | None = None,
    artifact_id: UUID | None = None,
    status_filter: str = "pending",
) -> ExtractDocumentsStandaloneResult:
    settings = settings or get_settings()
    if status_filter not in _ALLOWED_STATUS:
        raise ValueError(
            f"status_filter must be one of {sorted(_ALLOWED_STATUS)}, got {status_filter!r}"
        )
    lim = limit if limit is not None else settings.extract_max_documents
    out: ExtractDocumentsStandaloneResult = {
        "processed": 0,
        "ok": 0,
        "failed": 0,
        "total_chunks": 0,
        "needs_review_marked": 0,
        "artifact_ids": [],
        "status_filter": status_filter,
    }
    async with standalone_session(settings) as session:
        if artifact_id is not None:
            q = await session.execute(
                select(DocumentArtifact).where(DocumentArtifact.id == artifact_id)
            )
            rows = list(q.scalars().all())
        else:
            stmt = select(DocumentArtifact).order_by(DocumentArtifact.created_at.asc())
            stmt = _apply_extract_status_filter(stmt, status_filter)
            stmt = stmt.limit(lim)
            q = await session.execute(stmt)
            rows = list(q.scalars().all())

        if artifact_id is not None and not rows:
            raise ValueError(f"document_artifact not found: {artifact_id}")

        async with httpx.AsyncClient(timeout=settings.documents_http_timeout) as client:
            for art in rows:
                st = await extract_one_artifact(session, client, settings, art)
                out["processed"] += 1
                out["artifact_ids"].append(str(art.id))
                if st["status"] == "ok":
                    out["ok"] += 1
                    out["total_chunks"] += int(st.get("chunks") or 0)
                    if st.get("needs_review"):
                        out["needs_review_marked"] += 1
                else:
                    out["failed"] += 1
        await session.commit()
    return out
