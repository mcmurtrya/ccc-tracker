from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from citycouncil.config import Settings, get_settings


def make_engine(settings: Settings | None = None):
    settings = settings or get_settings()
    return create_async_engine(settings.database_url, echo=False)


def make_session_factory(engine: AsyncEngine | None = None):
    """Return an async session factory. Pass ``engine`` (as FastAPI does); if omitted, a new engine is created."""
    eng = engine or make_engine()
    return async_sessionmaker(eng, expire_on_commit=False, class_=AsyncSession)


@asynccontextmanager
async def standalone_session(settings: Settings) -> AsyncIterator[AsyncSession]:
    """Async session bound to one engine; disposes the engine when the block exits.

    Use for CLI / one-off jobs: caller commits or rolls back explicitly.
    """
    engine = make_engine(settings)
    factory = make_session_factory(engine)
    try:
        async with factory() as session:
            yield session
    finally:
        await engine.dispose()
