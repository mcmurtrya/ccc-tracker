"""Email alert subscriptions."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from citycouncil.db.base import Base
from citycouncil.db.models.common import utc_now


class AlertSubscription(Base):
    """Email alert subscription (filters mirror /activity + optional q)."""

    __tablename__ = "alert_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    secret_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    label: Mapped[str | None] = mapped_column(String(200))
    filters: Mapped[dict] = mapped_column(JSONB, default=lambda: {})
    active: Mapped[bool] = mapped_column(default=True)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
