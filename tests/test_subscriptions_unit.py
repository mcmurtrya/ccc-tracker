"""Unit tests for :mod:`citycouncil.subscriptions` (async mocks)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from citycouncil.subscriptions import create_subscription, unsubscribe_by_token


@pytest.mark.asyncio
async def test_create_subscription_inserts_normalized_email() -> None:
    session = MagicMock()
    r = MagicMock()
    r.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=r)
    session.flush = AsyncMock()
    row = await create_subscription(
        session,
        email="  User@Example.COM ",
        label="news",
        filters={"ward": 1},
    )
    assert row.email == "user@example.com"
    assert row.label == "news"
    assert row.filters == {"ward": 1}
    session.add.assert_called_once()
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_subscription_duplicate_email() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = object()
    session.execute = AsyncMock(return_value=result)
    with pytest.raises(ValueError, match="already subscribed"):
        await create_subscription(session, email="a@b.com", label=None, filters={})


@pytest.mark.asyncio
async def test_unsubscribe_unknown_token() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)
    assert await unsubscribe_by_token(session, "nope") is False


@pytest.mark.asyncio
async def test_unsubscribe_ok() -> None:
    session = AsyncMock()
    row = MagicMock()
    row.active = True
    result = MagicMock()
    result.scalar_one_or_none.return_value = row
    session.execute = AsyncMock(return_value=result)
    assert await unsubscribe_by_token(session, "tok") is True
    assert row.active is False
