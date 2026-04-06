"""CSV import staging (P2-301)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as PgEnum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from citycouncil.db.base import Base
from citycouncil.db.models.common import utc_now
from citycouncil.db.models.enums import CsvStagingRowStatus


class CsvImportBatch(Base):
    __tablename__ = "csv_import_batches"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(512))
    file_sha256: Mapped[str] = mapped_column(String(64), index=True)
    row_count: Mapped[int] = mapped_column(Integer)
    accepted_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_file_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_db_count: Mapped[int] = mapped_column(Integer, default=0)
    invalid_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    notes: Mapped[str | None] = mapped_column(Text)

    rows: Mapped[list["CsvImportStagingRow"]] = relationship(back_populates="batch")


class CsvImportStagingRow(Base):
    __tablename__ = "csv_import_staging_rows"
    __table_args__ = (UniqueConstraint("batch_id", "row_number", name="uq_csv_staging_batch_rownum"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("csv_import_batches.id", ondelete="CASCADE"), index=True)
    row_number: Mapped[int] = mapped_column(Integer)
    dedupe_key: Mapped[str] = mapped_column(String(512), index=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[CsvStagingRowStatus] = mapped_column(
        PgEnum(CsvStagingRowStatus, name="csv_staging_row_status", create_type=True),
        default=CsvStagingRowStatus.accepted,
    )
    errors: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    promotion_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    batch: Mapped[CsvImportBatch] = relationship(back_populates="rows")
