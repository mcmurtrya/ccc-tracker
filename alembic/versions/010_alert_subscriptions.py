"""alert_subscriptions for topic / saved-search alerts (Phase 5)

Revision ID: 010
Revises: 009
Create Date: 2026-04-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "alert_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("secret_token", sa.String(64), nullable=False),
        sa.Column("label", sa.String(200), nullable=True),
        sa.Column("filters", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_alert_subscriptions_email", "alert_subscriptions", ["email"], unique=True)
    op.create_index("ix_alert_subscriptions_secret_token", "alert_subscriptions", ["secret_token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_alert_subscriptions_secret_token", table_name="alert_subscriptions")
    op.drop_index("ix_alert_subscriptions_email", table_name="alert_subscriptions")
    op.drop_table("alert_subscriptions")
