from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Literal, TypedDict

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from citycouncil.config import Settings, get_settings
from citycouncil.db.session import standalone_session
from citycouncil.ingest.dlq import record_dlq
from citycouncil.ingest.elms_adapter import adapt_elms_poll_response
from citycouncil.ingest.elms_enrich import maybe_enrich_poll_payload
from citycouncil.ingest.normalize import ingest_payload


class PollCycleResult(TypedDict):
    """Successful return from :func:`run_poll_cycle` (errors raise)."""

    status: Literal["ok"]
    ingested_meeting_ids: list[str]


async def _load_fixture(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Fixture not found: {p.resolve()}")
    return json.loads(p.read_text(encoding="utf-8"))


async def _fetch_http(settings: Settings) -> dict[str, Any]:
    # Official Swagger: GET /meeting with OData-style $top / $skip (not /meetings).
    url = settings.elms_api_base.rstrip("/") + "/meeting"
    params: dict[str, str] = {"$top": str(settings.elms_poll_top)}
    if settings.elms_poll_skip:
        params["$skip"] = str(settings.elms_poll_skip)
    delay = 1.0
    last_err: Exception | None = None
    async with httpx.AsyncClient(timeout=settings.poller_timeout_seconds) as client:
        for attempt in range(settings.poller_max_retries):
            try:
                resp = await client.get(url, params=params)
                if resp.status_code == 304:
                    return {"meetings": []}
                resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPError, ValueError, json.JSONDecodeError) as e:
                last_err = e
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30.0)
        assert last_err is not None
        raise last_err


async def fetch_payload(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    if settings.poller_use_fixture:
        return await _load_fixture(settings.poller_fixture_path)
    raw = await _fetch_http(settings)
    adapted = adapt_elms_poll_response(raw)
    if settings.elms_enrich_detail:
        async with httpx.AsyncClient(timeout=settings.poller_timeout_seconds) as client:
            adapted = await maybe_enrich_poll_payload(client, settings, adapted)
    return adapted


async def run_poll_cycle(
    session: AsyncSession,
    settings: Settings | None = None,
) -> PollCycleResult:
    settings = settings or get_settings()
    payload: dict[str, Any] | None = None
    try:
        payload = await fetch_payload(settings)
        ids = await ingest_payload(session, payload)
        return {"status": "ok", "ingested_meeting_ids": [str(i) for i in ids]}
    except Exception as e:
        await session.rollback()
        snap: dict[str, Any]
        if isinstance(payload, dict):
            snap = payload
        elif settings.poller_use_fixture:
            try:
                snap = await _load_fixture(settings.poller_fixture_path)
            except Exception:
                snap = {"note": "fixture_unavailable"}
        else:
            snap = {"elms_api_base": settings.elms_api_base, "note": "fetch_or_parse_failed"}
        await record_dlq(session, source="elms_poll", payload=snap, error=repr(e))
        await session.commit()
        raise


async def run_poll_standalone(settings: Settings | None = None) -> PollCycleResult:
    settings = settings or get_settings()
    async with standalone_session(settings) as session:
        try:
            result = await run_poll_cycle(session, settings)
            await session.commit()
            return result
        except Exception:
            # After a failed flush/execute the session requires rollback before reuse.
            await session.rollback()
            raise
