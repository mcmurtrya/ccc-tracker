"""Integration tests: Postgres + Alembic + ingest flows.

Run against Docker testcontainers (default) or a real URL::

    CITYCOUNCIL_INTEGRATION_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/dbname \\
      pytest tests/integration -m integration

Create the database first if needed. Migrations run once per session.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _to_asyncpg_url(url: str) -> str:
    for prefix in ("postgresql+psycopg2://", "postgresql://"):
        if url.startswith(prefix):
            return url.replace(prefix, "postgresql+asyncpg://", 1)
    if url.startswith("postgresql+asyncpg://"):
        return url
    raise ValueError(f"Unsupported postgres URL scheme: {url[:40]}...")


def _apply_migrations(async_url: str) -> None:
    env = os.environ.copy()
    env["CITYCOUNCIL_DATABASE_URL"] = async_url
    subprocess.check_call(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env=env,
    )


@pytest.fixture(scope="session")
def postgres_url() -> str:
    """Yields async SQLAlchemy URL; applies Alembic migrations once."""
    explicit = os.environ.get("CITYCOUNCIL_INTEGRATION_DATABASE_URL")
    if explicit:
        url = _to_asyncpg_url(explicit.strip())
        _apply_migrations(url)
        yield url
        return

    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("Install dev deps: uv sync (includes testcontainers)")

    try:
        container = PostgresContainer("pgvector/pgvector:pg16")
        container.start()
    except Exception as e:
        pytest.skip(
            f"Docker/testcontainers unavailable ({e!s}). "
            "Set CITYCOUNCIL_INTEGRATION_DATABASE_URL to run integration tests."
        )

    raw = container.get_connection_url()
    async_url = _to_asyncpg_url(raw)
    try:
        _apply_migrations(async_url)
        yield async_url
    finally:
        container.stop()
