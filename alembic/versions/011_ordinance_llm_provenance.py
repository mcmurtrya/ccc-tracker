"""Ordinance LLM provenance (Phase 6 trust layer)

Revision ID: 011
Revises: 010
Create Date: 2026-04-08

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ordinances", sa.Column("llm_summary_model", sa.String(length=128), nullable=True))
    op.add_column("ordinances", sa.Column("llm_summary_prompt_version", sa.String(length=64), nullable=True))
    op.add_column("ordinances", sa.Column("llm_summarized_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("ordinances", "llm_summarized_at")
    op.drop_column("ordinances", "llm_summary_prompt_version")
    op.drop_column("ordinances", "llm_summary_model")
