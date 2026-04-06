"""ELMS-aligned core entities: members, meetings, ordinances, agenda, votes."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum as PgEnum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from citycouncil.db.base import Base
from citycouncil.db.models.common import utc_now
from citycouncil.db.models.enums import VotePosition


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
