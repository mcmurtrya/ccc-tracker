"""Document artifacts and chunks (extraction + RAG embeddings)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as PgEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from citycouncil.constants import PGVECTOR_EMBEDDING_DIMENSION
from citycouncil.db.base import Base
from citycouncil.db.models.common import utc_now
from citycouncil.db.models.elms_core import Meeting
from citycouncil.db.models.enums import ParseStatus


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
