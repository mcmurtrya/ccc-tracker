"""csv import staging (P2-301)

Revision ID: 002
Revises: 001
Create Date: 2026-04-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    staging_status = postgresql.ENUM(
        "accepted",
        "duplicate_file",
        "duplicate_db",
        "invalid",
        name="csv_staging_row_status",
        create_type=False,
    )
    bind = op.get_bind()
    staging_status.create(bind, checkfirst=True)

    op.create_table(
        "csv_import_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("accepted_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_file_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_db_count", sa.Integer(), nullable=False),
        sa.Column("invalid_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_csv_import_batches_file_sha256"), "csv_import_batches", ["file_sha256"], unique=False)

    op.create_table(
        "csv_import_staging_rows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("dedupe_key", sa.String(length=512), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", staging_status, nullable=False),
        sa.Column("errors", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["csv_import_batches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "row_number", name="uq_csv_staging_batch_rownum"),
    )
    op.create_index(op.f("ix_csv_import_staging_rows_batch_id"), "csv_import_staging_rows", ["batch_id"], unique=False)
    op.create_index(op.f("ix_csv_import_staging_rows_dedupe_key"), "csv_import_staging_rows", ["dedupe_key"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_csv_import_staging_rows_dedupe_key"), table_name="csv_import_staging_rows")
    op.drop_index(op.f("ix_csv_import_staging_rows_batch_id"), table_name="csv_import_staging_rows")
    op.drop_table("csv_import_staging_rows")
    op.drop_index(op.f("ix_csv_import_batches_file_sha256"), table_name="csv_import_batches")
    op.drop_table("csv_import_batches")
    op.execute(sa.text("DROP TYPE IF EXISTS csv_staging_row_status"))
