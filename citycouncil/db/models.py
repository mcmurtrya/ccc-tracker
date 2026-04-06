from __future__ import annotations

import enum
import uuid
from datetime import date, datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy import Enum as PgEnum, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from citycouncil.constants import PGVECTOR_EMBEDDING_DIMENSION
from citycouncil.db.base import Base


class VotePosition(str, enum.Enum):
    aye = "aye"
    nay = "nay"
    abstain = "abstain"
    absent = "absent"


class ParseStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    ok = "ok"
    failed = "failed"


class Member(Base):
    __tablename__ = "members"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(500))
    ward: Mapped[int | None] = mapped_column(Integer)
    body: Mapped[str | None] = mapped_column(String(100))
    term_start: Mapped[date | None] = mapped_column(Date)
    term_end: Mapped[date | None] = mapped_column(Date)
    raw_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    meeting_date: Mapped[date] = mapped_column(Date)
    body: Mapped[str | None] = mapped_column(String(200))
    location: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str | None] = mapped_column(String(100))
    raw_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    agenda_items: Mapped[list[AgendaItem]] = relationship(back_populates="meeting")
    votes: Mapped[list[Vote]] = relationship(back_populates="meeting")
    document_chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="meeting")


class Ordinance(Base):
    __tablename__ = "ordinances"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    title: Mapped[str] = mapped_column(Text)
    sponsor_external_id: Mapped[str | None] = mapped_column(String(255), index=True)
    introduced_date: Mapped[date | None] = mapped_column(Date)
    topic_tags: Mapped[list[str] | None] = mapped_column(ARRAY(String(64)))
    llm_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_tags: Mapped[list[str] | None] = mapped_column(ARRAY(String(64)), nullable=True)
    llm_summary_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    llm_summary_prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    llm_summarized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    agenda_items: Mapped[list[AgendaItem]] = relationship(back_populates="ordinance")
    votes: Mapped[list[Vote]] = relationship(back_populates="ordinance")


class AgendaItem(Base):
    __tablename__ = "agenda_items"
    __table_args__ = (UniqueConstraint("meeting_id", "sequence", name="uq_agenda_meeting_sequence"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meetings.id", ondelete="CASCADE"), index=True)
    ordinance_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ordinances.id", ondelete="SET NULL"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    raw_text: Mapped[str | None] = mapped_column(Text)
    raw_json: Mapped[dict | None] = mapped_column(JSONB)

    meeting: Mapped[Meeting] = relationship(back_populates="agenda_items")
    ordinance: Mapped[Ordinance | None] = relationship(back_populates="agenda_items")


class Vote(Base):
    __tablename__ = "votes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    ordinance_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ordinances.id", ondelete="CASCADE"), index=True)
    meeting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meetings.id", ondelete="CASCADE"), index=True)
    result: Mapped[str | None] = mapped_column(String(100))
    ayes: Mapped[int | None] = mapped_column(Integer)
    nays: Mapped[int | None] = mapped_column(Integer)
    abstentions: Mapped[int | None] = mapped_column(Integer)
    raw_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    meeting: Mapped[Meeting] = relationship(back_populates="votes")
    ordinance: Mapped[Ordinance] = relationship(back_populates="votes")
    vote_members: Mapped[list[VoteMember]] = relationship(back_populates="vote")


class VoteMember(Base):
    __tablename__ = "vote_members"
    __table_args__ = (UniqueConstraint("vote_id", "member_id", name="uq_vote_member"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    vote_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("votes.id", ondelete="CASCADE"), index=True)
    member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"), index=True)
    position: Mapped[VotePosition] = mapped_column(PgEnum(VotePosition, name="vote_position", create_type=True))

    vote: Mapped[Vote] = relationship(back_populates="vote_members")
    member: Mapped[Member] = relationship()


class DocumentArtifact(Base):
    __tablename__ = "document_artifacts"
    __table_args__ = (
        Index(
            "uq_document_artifacts_meeting_source",
            "meeting_id",
            "source_url",
            unique=True,
            postgresql_where=text("source_url IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meeting_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("meetings.id", ondelete="SET NULL"))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    uri: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    attachment_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    bytes_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    parse_status: Mapped[ParseStatus] = mapped_column(
        PgEnum(ParseStatus, name="parse_status", create_type=True),
        default=ParseStatus.pending,
    )
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    local_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="artifact",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_artifact_id", "chunk_index", name="uq_document_chunks_artifact_ord"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_artifacts.id", ondelete="CASCADE"), index=True
    )
    meeting_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("meetings.id", ondelete="SET NULL"), index=True, nullable=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    body: Mapped[str] = mapped_column(Text)
    extractor_version: Mapped[str] = mapped_column(String(64), default="pymupdf")
    embedding: Mapped[list[float] | None] = mapped_column(ARRAY(Float), nullable=True)
    embedding_vector: Mapped[list[float] | None] = mapped_column(
        Vector(PGVECTOR_EMBEDDING_DIMENSION),
        nullable=True,
    )
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    artifact: Mapped[DocumentArtifact] = relationship(back_populates="chunks")
    meeting: Mapped[Meeting | None] = relationship(back_populates="document_chunks")


class LlmJob(Base):
    """Async job queue for embeddings / LLM (LLM-201)."""

    __tablename__ = "llm_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class IngestState(Base):
    __tablename__ = "ingest_state"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


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


class IngestDLQ(Base):
    __tablename__ = "ingest_dlq"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB)
    error: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class CsvStagingRowStatus(str, enum.Enum):
    """P2-301 staging row outcome."""

    accepted = "accepted"
    duplicate_file = "duplicate_file"
    duplicate_db = "duplicate_db"
    invalid = "invalid"


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
