"""document_artifacts: ELMS file metadata for download + dedupe

Revision ID: 004
Revises: 003
Create Date: 2026-04-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("document_artifacts", sa.Column("source_url", sa.Text(), nullable=True))
    op.add_column("document_artifacts", sa.Column("file_name", sa.String(length=512), nullable=True))
    op.add_column("document_artifacts", sa.Column("attachment_type", sa.String(length=128), nullable=True))
    op.add_column("document_artifacts", sa.Column("bytes_size", sa.Integer(), nullable=True))
    op.add_column(
        "document_artifacts",
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index(
        "uq_document_artifacts_meeting_source",
        "document_artifacts",
        ["meeting_id", "source_url"],
        unique=True,
        postgresql_where=sa.text("source_url IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_document_artifacts_meeting_source", table_name="document_artifacts")
    op.drop_column("document_artifacts", "raw_json")
    op.drop_column("document_artifacts", "bytes_size")
    op.drop_column("document_artifacts", "attachment_type")
    op.drop_column("document_artifacts", "file_name")
    op.drop_column("document_artifacts", "source_url")
