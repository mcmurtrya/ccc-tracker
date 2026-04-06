"""End-to-end: migrate → poll (fixture) → load-csv → promote."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from sqlalchemy import func, select

from citycouncil.config import get_settings
from citycouncil.csv_loader import load_csv_standalone
from citycouncil.csv_promote import promote_standalone
from citycouncil.db.models import CsvImportStagingRow, Meeting, Ordinance
from citycouncil.db.session import make_engine, make_session_factory
from citycouncil.ingest.poller import run_poll_standalone

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_POLL = ROOT / "fixtures" / "sample_elms_response.json"
FIXTURE_CSV = ROOT / "fixtures" / "sample_backfill.csv"


async def _count_core() -> tuple[int, int, int]:
    settings = get_settings()
    engine = make_engine(settings)
    factory = make_session_factory(engine)
    async with factory() as session:
        meetings = int(await session.scalar(select(func.count()).select_from(Meeting)) or 0)
        ordinances = int(await session.scalar(select(func.count()).select_from(Ordinance)) or 0)
        promoted = int(
            await session.scalar(
                select(func.count())
                .select_from(CsvImportStagingRow)
                .where(CsvImportStagingRow.promoted_at.isnot(None))
            )
            or 0
        )
    await engine.dispose()
    return meetings, ordinances, promoted


@pytest.mark.integration
def test_migrate_poll_load_csv_promote(postgres_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CITYCOUNCIL_DATABASE_URL", postgres_url)
    monkeypatch.setenv("CITYCOUNCIL_POLLER_USE_FIXTURE", "1")
    monkeypatch.setenv("CITYCOUNCIL_POLLER_FIXTURE_PATH", str(FIXTURE_POLL))

    poll_out = asyncio.run(run_poll_standalone())
    assert poll_out["status"] == "ok"
    assert poll_out["ingested_meeting_ids"]

    m1, o1, _ = asyncio.run(_count_core())
    assert m1 >= 1
    assert o1 >= 1

    csv_out = asyncio.run(load_csv_standalone(str(FIXTURE_CSV)))
    assert csv_out.accepted_count >= 1

    prom_out = asyncio.run(promote_standalone())
    assert prom_out.promoted >= 1

    m2, o2, promoted_rows = asyncio.run(_count_core())
    assert m2 >= m1
    assert o2 > o1
    assert promoted_rows >= 1
