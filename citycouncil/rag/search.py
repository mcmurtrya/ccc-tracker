"""Semantic search over ``document_chunks`` using pgvector cosine distance (RAG)."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from citycouncil.config import Settings
from citycouncil.constants import PGVECTOR_EMBEDDING_DIMENSION
from citycouncil.ingest.embeddings_huggingface import embed_texts_huggingface_batch
from citycouncil.ingest.hf_embedding_params import hf_feature_extraction_call_kwargs


def _vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(str(f) for f in vec) + "]"


def body_preview(text: str, max_chars: int) -> str:
    """Short snippet for API consumers (residents/reporters); full text remains in ``body``."""
    t = text.strip()
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 1].rstrip() + "…"


def citations_from_chunk_results(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Explicit citation list for trust / UI (subset of each hit, no body text)."""
    out: list[dict[str, Any]] = []
    for it in items:
        out.append(
            {
                "chunk_id": it["chunk_id"],
                "document_artifact_id": it["document_artifact_id"],
                "meeting_id": it.get("meeting_id"),
                "page_number": it.get("page_number"),
                "score": it.get("score"),
            }
        )
    return out


async def search_document_chunks(
    session: AsyncSession,
    settings: Settings,
    query: str,
    *,
    limit: int = 10,
    meeting_id: UUID | None = None,
) -> list[dict[str, Any]]:
    """Embed ``query`` and return nearest chunks by cosine distance (lower is better)."""
    if not settings.huggingface_token:
        raise ValueError("CITYCOUNCIL_HUGGINGFACE_TOKEN is not set")
    if settings.embedding_dimensions != PGVECTOR_EMBEDDING_DIMENSION:
        raise ValueError(
            f"RAG pgvector is built for dimension {PGVECTOR_EMBEDDING_DIMENSION}; "
            f"set CITYCOUNCIL_EMBEDDING_DIMENSIONS={PGVECTOR_EMBEDDING_DIMENSION} "
            "and re-embed chunks (same model as indexing)."
        )
    q = query.strip()
    if not q:
        return []

    embed_kw = hf_feature_extraction_call_kwargs(settings, for_query=True)
    vecs = await asyncio.to_thread(
        embed_texts_huggingface_batch,
        [q],
        **embed_kw,
    )
    qv = vecs[0]
    lit = _vector_literal(qv)

    preview_n = settings.search_chunk_preview_chars

    # asyncpg cannot infer the type of a bound NULL for ``(:mid IS NULL OR ...)``; branch the SQL.
    # Join meetings + document_artifacts for reporter/resident context (Phase 2).
    base_select = """
            SELECT dc.id, dc.chunk_index, dc.body, dc.page_number, dc.meeting_id, dc.document_artifact_id,
                   dc.embedding_vector <=> CAST(:qv AS vector) AS distance,
                   da.file_name AS artifact_file_name,
                   da.source_url AS artifact_source_url,
                   da.uri AS artifact_uri,
                   m.id AS join_meeting_id,
                   m.meeting_date AS join_meeting_date,
                   m.body AS join_meeting_body,
                   m.location AS join_meeting_location,
                   m.status AS join_meeting_status
            FROM document_chunks dc
            LEFT JOIN document_artifacts da ON da.id = dc.document_artifact_id
            LEFT JOIN meetings m ON m.id = dc.meeting_id
            WHERE dc.embedding_vector IS NOT NULL
    """
    if meeting_id is None:
        sql = text(
            base_select
            + """
            ORDER BY dc.embedding_vector <=> CAST(:qv AS vector)
            LIMIT :lim
            """
        )
        params: dict[str, object] = {"qv": lit, "lim": limit}
    else:
        sql = text(
            base_select
            + """
              AND dc.meeting_id = :mid
            ORDER BY dc.embedding_vector <=> CAST(:qv AS vector)
            LIMIT :lim
            """
        )
        params = {"qv": lit, "lim": limit, "mid": meeting_id}
    result = await session.execute(sql, params)
    rows = result.mappings().all()
    out: list[dict[str, Any]] = []
    for r in rows:
        dist = float(r["distance"])
        score = 1.0 - dist
        body = r["body"]
        meeting_payload = None
        mid = r["meeting_id"]
        if mid is not None and r["join_meeting_id"] is not None:
            meeting_payload = {
                "id": str(r["join_meeting_id"]),
                "meeting_date": r["join_meeting_date"].isoformat()
                if r["join_meeting_date"]
                else None,
                "body": r["join_meeting_body"],
                "location": r["join_meeting_location"],
                "status": r["join_meeting_status"],
            }
        document_payload = {
            "file_name": r["artifact_file_name"],
            "source_url": r["artifact_source_url"],
            "uri": r["artifact_uri"],
        }
        out.append(
            {
                "chunk_id": str(r["id"]),
                "chunk_index": int(r["chunk_index"]),
                "body": body,
                "body_preview": body_preview(body, preview_n),
                "page_number": r["page_number"],
                "meeting_id": str(mid) if mid else None,
                "meeting": meeting_payload,
                "document_artifact_id": str(r["document_artifact_id"]),
                "document": document_payload,
                "distance": dist,
                "score": score,
            }
        )
    return out
