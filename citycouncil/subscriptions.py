"""Alert subscriptions (email digest hook; RSS is primary public surface)."""

from __future__ import annotations

import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from citycouncil.db.models import AlertSubscription


async def create_subscription(
    session: AsyncSession,
    *,
    email: str,
    label: str | None,
    filters: dict[str, object],
) -> AlertSubscription:
    email_norm = email.strip().lower()
    existing = await session.execute(select(AlertSubscription).where(AlertSubscription.email == email_norm))
    if existing.scalar_one_or_none() is not None:
        raise ValueError("email already subscribed")
    token = secrets.token_urlsafe(48)[:64]
    row = AlertSubscription(
        email=email_norm,
        secret_token=token,
        label=label,
        filters=filters,
        active=True,
    )
    session.add(row)
    await session.flush()
    return row


async def unsubscribe_by_token(session: AsyncSession, token: str) -> bool:
    q = await session.execute(select(AlertSubscription).where(AlertSubscription.secret_token == token))
    row = q.scalar_one_or_none()
    if row is None:
        return False
    row.active = False
    await session.flush()
    return True
