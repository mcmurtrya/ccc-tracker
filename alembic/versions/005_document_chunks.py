"""document_chunks + parse_error on document_artifacts (TXT-101/102)

Revision ID: 005
Revises: 004
Create Date: 2026-04-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("document_artifacts", sa.Column("parse_error", sa.Text(), nullable=True))

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_artifact_id", sa.Uuid(), nullable=False),
        sa.Column("meeting_id", sa.Uuid(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("extractor_version", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_artifact_id"], ["document_artifacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_artifact_id", "chunk_index", name="uq_document_chunks_artifact_ord"),
    )
    op.create_index(
        op.f("ix_document_chunks_document_artifact_id"),
        "document_chunks",
        ["document_artifact_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_chunks_meeting_id"),
        "document_chunks",
        ["meeting_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_document_chunks_meeting_id"), table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_document_artifact_id"), table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_column("document_artifacts", "parse_error")
