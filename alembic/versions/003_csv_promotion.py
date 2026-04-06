"""csv staging promotion columns

Revision ID: 003
Revises: 002
Create Date: 2026-04-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "csv_import_staging_rows",
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "csv_import_staging_rows",
        sa.Column("promotion_error", sa.Text(), nullable=True),
    )
    op.create_index(
        op.f("ix_csv_import_staging_rows_promoted_at"),
        "csv_import_staging_rows",
        ["promoted_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_csv_import_staging_rows_promoted_at"), table_name="csv_import_staging_rows")
    op.drop_column("csv_import_staging_rows", "promotion_error")
    op.drop_column("csv_import_staging_rows", "promoted_at")
