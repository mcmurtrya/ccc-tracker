from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from citycouncil.db.models import IngestDLQ


async def record_dlq(session: AsyncSession, source: str, payload: dict, error: str) -> None:
    session.add(IngestDLQ(source=source, payload=payload, error=error[:20000]))
    await session.flush()
