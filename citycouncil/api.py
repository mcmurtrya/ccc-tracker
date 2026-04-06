from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Literal
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from citycouncil.activity_query import run_activity_feed
from citycouncil.auth import verify_admin
from citycouncil.config import get_settings
from citycouncil.csv_promote import promote_accepted_staging, reconciliation_report
from citycouncil.db.models import IngestDLQ, Meeting
from citycouncil.documents_stats import document_artifact_stats
from citycouncil.db.session import make_engine, make_session_factory
from citycouncil.export_data import (
    load_meetings_ordered,
    load_ordinances_ordered,
    load_vote_members_with_refs,
    load_votes_with_refs,
    meetings_csv,
    meetings_json,
    ordinances_csv,
    ordinances_json,
    vote_members_csv,
    vote_members_json,
    votes_csv,
    votes_json,
)
from citycouncil.ingest.poller import run_poll_cycle
from citycouncil.meetings_detail import fetch_meeting_detail
from citycouncil.llm.ordinance_summarize import summarize_ordinance
from citycouncil.ordinance_public import fetch_ordinance_public
from citycouncil.rag.search import citations_from_chunk_results, search_document_chunks
from citycouncil.rss import render_activity_rss
from citycouncil.search_limits import clamp_search_limit
from citycouncil.subscriptions import create_subscription, unsubscribe_by_token


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    engine = make_engine(settings)
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    try:
        yield
    finally:
        await engine.dispose()


app = FastAPI(title="City Council Data API", version="0.1.0", lifespan=lifespan)


async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


SessionDep = Annotated[AsyncSession, Depends(get_session)]

admin_router = APIRouter(prefix="/admin", dependencies=[Depends(verify_admin)])


class SubscriptionCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    label: str | None = None
    types: str | None = None
    q: str | None = None


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/search/chunks")
async def search_chunks(
    session: SessionDep,
    q: str = Query(..., min_length=1, description="Natural-language query"),
    limit: int | None = Query(
        default=None,
        ge=1,
        le=100,
        description="Result count; clamped to CITYCOUNCIL_SEARCH_MAX_LIMIT (Field max 100).",
    ),
    meeting_id: UUID | None = Query(default=None, description="Restrict to chunks linked to this meeting id"),
) -> dict[str, object]:
    """Semantic search over embedded ``document_chunks`` (pgvector cosine distance).

    Each result includes ``body_preview``, nested ``meeting`` (when linked), and ``document``
    file/URL fields from ``document_artifacts`` for verification. ``citations`` repeats
    chunk ids and scores for grounding; ``disclaimer`` reminds clients to verify sources.
    """
    settings = get_settings()
    if not settings.huggingface_token:
        raise HTTPException(
            status_code=503,
            detail="CITYCOUNCIL_HUGGINGFACE_TOKEN is not set",
        )
    lim = clamp_search_limit(settings, limit)
    try:
        items = await search_document_chunks(
            session,
            settings,
            q,
            limit=lim,
            meeting_id=meeting_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    citations = citations_from_chunk_results(items)
    return {
        "query": q,
        "count": len(items),
        "results": items,
        "citations": citations,
        "embedding_model": settings.huggingface_embedding_model,
        "disclaimer": settings.search_trust_disclaimer,
    }


@app.get("/meetings")
async def list_meetings(
    session: SessionDep,
    limit: int = 50,
) -> dict[str, object]:
    q = await session.execute(
        select(Meeting).order_by(Meeting.meeting_date.desc()).limit(min(limit, 200))
    )
    rows = q.scalars().all()
    return {
        "count": len(rows),
        "meetings": [
            {
                "id": str(m.id),
                "external_id": m.external_id,
                "meeting_date": m.meeting_date.isoformat(),
                "body": m.body,
                "location": m.location,
                "status": m.status,
            }
            for m in rows
        ],
    }


@app.get("/activity")
async def activity_feed(
    session: SessionDep,
    since: str | None = Query(
        default=None,
        description="ISO8601 lower bound (UTC). Omit to use CITYCOUNCIL_ACTIVITY_DEFAULT_SINCE_DAYS.",
    ),
    until: str | None = Query(default=None, description="Optional ISO8601 upper bound (UTC)"),
    types: str | None = Query(
        default=None,
        description="Comma-separated: meetings, ordinances, documents (default: all)",
    ),
    limit: int | None = Query(default=None, ge=1, le=1000),
    offset: int = Query(default=0, ge=0, le=100_000),
    filter_q: str | None = Query(
        default=None,
        alias="q",
        description="Case-insensitive substring filter on titles, tags, meeting text, document names",
    ),
) -> dict[str, object]:
    """Reverse-chronological feed of updated meetings/ordinances and new document artifacts."""
    settings = get_settings()
    try:
        return await run_activity_feed(
            session,
            settings,
            since=since,
            until=until,
            types=types,
            limit=limit,
            offset=offset,
            filter_q=filter_q,
            rss=False,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/feed.xml", response_model=None)
async def activity_rss(
    request: Request,
    session: SessionDep,
    since: str | None = Query(
        default=None,
        description="ISO8601 lower bound (UTC). Omit to use CITYCOUNCIL_ACTIVITY_DEFAULT_SINCE_DAYS.",
    ),
    until: str | None = Query(default=None),
    types: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=100),
    filter_q: str | None = Query(default=None, alias="q"),
) -> Response:
    """RSS 2.0 mirror of ``/activity`` (for readers and reporters)."""
    settings = get_settings()
    try:
        payload = await run_activity_feed(
            session,
            settings,
            since=since,
            until=until,
            types=types,
            limit=limit,
            offset=0,
            filter_q=filter_q,
            rss=True,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    base = settings.public_base_url.rstrip("/")
    self_link = f"{request.url.scheme}://{request.url.netloc}{request.url.path}"
    xml = render_activity_rss(
        payload["items"],
        feed_title="City Council activity",
        feed_link=base,
        feed_description="Recent meetings, ordinances, and documents (City Council API).",
        self_link=self_link,
        base_url=base,
    )
    return Response(
        content=xml.encode("utf-8"),
        media_type="application/rss+xml; charset=utf-8",
    )


@app.get("/alerts/unsubscribe")
async def alerts_unsubscribe(session: SessionDep, token: str = Query(..., min_length=8)) -> dict[str, str]:
    """Deactivate an email alert subscription (token from POST /admin/subscriptions)."""
    await unsubscribe_by_token(session, token)
    return {"status": "ok"}


@app.get("/ordinances/{ordinance_id}")
async def get_ordinance(
    session: SessionDep,
    ordinance_id: UUID,
) -> dict[str, object]:
    """Public ordinance record (title, tags, optional LLM summary)."""
    payload = await fetch_ordinance_public(session, ordinance_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Ordinance not found")
    return payload


@app.get("/meetings/{meeting_id}")
async def get_meeting(
    session: SessionDep,
    meeting_id: UUID,
) -> dict[str, object]:
    """Public meeting detail: agenda lines, votes with roll call, linked PDF metadata (resident/reporter API)."""
    payload = await fetch_meeting_detail(session, meeting_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return payload


@admin_router.post("/poll")
async def admin_poll(session: SessionDep) -> dict[str, object]:
    return await run_poll_cycle(session)


@admin_router.post("/csv/promote")
async def admin_csv_promote(
    session: SessionDep,
    batch_id: UUID | None = Query(default=None),
) -> dict[str, object]:
    out = await promote_accepted_staging(session, batch_id=batch_id)
    return {"promoted": out.promoted, "failed": out.failed}


@admin_router.get("/csv/reconcile")
async def admin_csv_reconcile(
    session: SessionDep,
    batch_id: UUID | None = Query(default=None),
) -> dict[str, object]:
    return await reconciliation_report(session, batch_id=batch_id)


@admin_router.get("/documents/stats")
async def admin_document_stats(session: SessionDep) -> dict[str, object]:
    """DOC-005: counts for document_artifacts and document_chunks."""
    return await document_artifact_stats(session)


@admin_router.get("/export/meetings", response_model=None)
async def admin_export_meetings(
    session: SessionDep,
    fmt: Literal["csv", "json"] = Query("csv", description="csv or json"),
) -> dict[str, object] | Response:
    """Bulk export of ``meetings`` (reporters / data journalism)."""
    rows = await load_meetings_ordered(session)
    if fmt == "json":
        return meetings_json(rows)
    return Response(
        content=meetings_csv(rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="meetings.csv"'},
    )


@admin_router.get("/export/ordinances", response_model=None)
async def admin_export_ordinances(
    session: SessionDep,
    fmt: Literal["csv", "json"] = Query("csv", description="csv or json"),
) -> dict[str, object] | Response:
    rows = await load_ordinances_ordered(session)
    if fmt == "json":
        return ordinances_json(rows)
    return Response(
        content=ordinances_csv(rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="ordinances.csv"'},
    )


@admin_router.get("/export/votes", response_model=None)
async def admin_export_votes(
    session: SessionDep,
    fmt: Literal["csv", "json"] = Query("csv", description="csv or json"),
) -> dict[str, object] | Response:
    rows = await load_votes_with_refs(session)
    if fmt == "json":
        return votes_json(rows)
    return Response(
        content=votes_csv(rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="votes.csv"'},
    )


@admin_router.get("/export/vote-members", response_model=None)
async def admin_export_vote_members(
    session: SessionDep,
    fmt: Literal["csv", "json"] = Query("csv", description="csv or json"),
) -> dict[str, object] | Response:
    """Roll-call rows: one row per member per vote."""
    rows = await load_vote_members_with_refs(session)
    if fmt == "json":
        return vote_members_json(rows)
    return Response(
        content=vote_members_csv(rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="vote_members.csv"'},
    )


@admin_router.post("/subscriptions", response_model=None)
async def admin_create_subscription(
    session: SessionDep,
    body: SubscriptionCreate,
) -> dict[str, object]:
    """Register an email alert subscription (digest sending requires separate SMTP automation)."""
    filters: dict[str, object] = {}
    if body.types:
        filters["types"] = body.types
    if body.q:
        filters["q"] = body.q
    try:
        row = await create_subscription(
            session,
            email=body.email,
            label=body.label,
            filters=filters,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {
        "id": str(row.id),
        "email": row.email,
        "unsubscribe_token": row.secret_token,
        "active": row.active,
    }


@admin_router.post("/ordinances/{ordinance_id}/summarize")
async def admin_ordinance_summarize(
    session: SessionDep,
    ordinance_id: UUID,
) -> dict[str, object]:
    """LLM-202: fill ``llm_summary`` and ``llm_tags`` via HF chat."""
    settings = get_settings()
    try:
        return await summarize_ordinance(session, settings, ordinance_id)
    except ValueError as e:
        msg = str(e).lower()
        status = 404 if "not found" in msg else 400
        raise HTTPException(status_code=status, detail=str(e)) from e
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"inference HTTP {e.response.status_code}",
        ) from e


@admin_router.get("/dlq")
async def list_dlq(
    session: SessionDep,
    limit: int = 20,
) -> dict[str, object]:
    q = await session.execute(
        select(IngestDLQ).order_by(IngestDLQ.created_at.desc()).limit(min(limit, 100))
    )
    rows = q.scalars().all()
    total = await session.scalar(select(func.count()).select_from(IngestDLQ))
    return {
        "total": int(total or 0),
        "items": [
            {
                "id": str(r.id),
                "source": r.source,
                "error": r.error[:500],
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
    }


app.include_router(admin_router)
