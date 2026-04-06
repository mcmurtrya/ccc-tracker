"""document_artifacts: local_path (DOC-004) + needs_review (TXT-104 scaffold)

Revision ID: 006
Revises: 005
Create Date: 2026-04-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("document_artifacts", sa.Column("local_path", sa.Text(), nullable=True))
    op.add_column(
        "document_artifacts",
        sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("document_artifacts", "needs_review")
    op.drop_column("document_artifacts", "local_path")
