"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-04-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # create_type=False: types are created explicitly below; avoids duplicate CREATE TYPE on create_table.
    vote_position = postgresql.ENUM("aye", "nay", "abstain", "absent", name="vote_position", create_type=False)
    parse_status = postgresql.ENUM("pending", "processing", "ok", "failed", name="parse_status", create_type=False)
    bind = op.get_bind()
    vote_position.create(bind, checkfirst=True)
    parse_status.create(bind, checkfirst=True)

    op.create_table(
        "members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("ward", sa.Integer(), nullable=True),
        sa.Column("body", sa.String(length=100), nullable=True),
        sa.Column("term_start", sa.Date(), nullable=True),
        sa.Column("term_end", sa.Date(), nullable=True),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_members_external_id"), "members", ["external_id"], unique=True)

    op.create_table(
        "meetings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("meeting_date", sa.Date(), nullable=False),
        sa.Column("body", sa.String(length=200), nullable=True),
        sa.Column("location", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=100), nullable=True),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_meetings_external_id"), "meetings", ["external_id"], unique=True)

    op.create_table(
        "ordinances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("sponsor_external_id", sa.String(length=255), nullable=True),
        sa.Column("introduced_date", sa.Date(), nullable=True),
        sa.Column("topic_tags", postgresql.ARRAY(sa.String(length=64)), nullable=True),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ordinances_external_id"), "ordinances", ["external_id"], unique=True)
    op.create_index(op.f("ix_ordinances_sponsor_external_id"), "ordinances", ["sponsor_external_id"], unique=False)

    op.create_table(
        "agenda_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("meeting_id", sa.Uuid(), nullable=False),
        sa.Column("ordinance_id", sa.Uuid(), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ordinance_id"], ["ordinances.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("meeting_id", "sequence", name="uq_agenda_meeting_sequence"),
    )
    op.create_index(op.f("ix_agenda_items_meeting_id"), "agenda_items", ["meeting_id"], unique=False)
    op.create_index(op.f("ix_agenda_items_ordinance_id"), "agenda_items", ["ordinance_id"], unique=False)

    op.create_table(
        "votes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("ordinance_id", sa.Uuid(), nullable=False),
        sa.Column("meeting_id", sa.Uuid(), nullable=False),
        sa.Column("result", sa.String(length=100), nullable=True),
        sa.Column("ayes", sa.Integer(), nullable=True),
        sa.Column("nays", sa.Integer(), nullable=True),
        sa.Column("abstentions", sa.Integer(), nullable=True),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ordinance_id"], ["ordinances.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_votes_external_id"), "votes", ["external_id"], unique=True)
    op.create_index(op.f("ix_votes_meeting_id"), "votes", ["meeting_id"], unique=False)
    op.create_index(op.f("ix_votes_ordinance_id"), "votes", ["ordinance_id"], unique=False)

    op.create_table(
        "vote_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vote_id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column("position", vote_position, nullable=False),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vote_id"], ["votes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vote_id", "member_id", name="uq_vote_member"),
    )
    op.create_index(op.f("ix_vote_members_member_id"), "vote_members", ["member_id"], unique=False)
    op.create_index(op.f("ix_vote_members_vote_id"), "vote_members", ["vote_id"], unique=False)

    op.create_table(
        "document_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("meeting_id", sa.Uuid(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("uri", sa.Text(), nullable=False),
        sa.Column("parse_status", parse_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_document_artifacts_sha256"), "document_artifacts", ["sha256"], unique=False)

    op.create_table(
        "ingest_state",
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )

    op.create_table(
        "ingest_dlq",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("ingest_dlq")
    op.drop_table("ingest_state")
    op.drop_index(op.f("ix_document_artifacts_sha256"), table_name="document_artifacts")
    op.drop_table("document_artifacts")
    op.drop_index(op.f("ix_vote_members_vote_id"), table_name="vote_members")
    op.drop_index(op.f("ix_vote_members_member_id"), table_name="vote_members")
    op.drop_table("vote_members")
    op.drop_index(op.f("ix_votes_ordinance_id"), table_name="votes")
    op.drop_index(op.f("ix_votes_meeting_id"), table_name="votes")
    op.drop_index(op.f("ix_votes_external_id"), table_name="votes")
    op.drop_table("votes")
    op.drop_index(op.f("ix_agenda_items_ordinance_id"), table_name="agenda_items")
    op.drop_index(op.f("ix_agenda_items_meeting_id"), table_name="agenda_items")
    op.drop_table("agenda_items")
    op.drop_index(op.f("ix_ordinances_sponsor_external_id"), table_name="ordinances")
    op.drop_index(op.f("ix_ordinances_external_id"), table_name="ordinances")
    op.drop_table("ordinances")
    op.drop_index(op.f("ix_meetings_external_id"), table_name="meetings")
    op.drop_table("meetings")
    op.drop_index(op.f("ix_members_external_id"), table_name="members")
    op.drop_table("members")

    op.execute(sa.text("DROP TYPE IF EXISTS parse_status"))
    op.execute(sa.text("DROP TYPE IF EXISTS vote_position"))
