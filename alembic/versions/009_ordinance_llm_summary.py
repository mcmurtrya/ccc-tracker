"""Ordinance LLM summary + tags (LLM-202)

Revision ID: 009
Revises: 008
Create Date: 2026-04-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ordinances", sa.Column("llm_summary", sa.Text(), nullable=True))
    op.add_column(
        "ordinances",
        sa.Column("llm_tags", postgresql.ARRAY(sa.String(length=64)), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ordinances", "llm_tags")
    op.drop_column("ordinances", "llm_summary")
