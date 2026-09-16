"""add durable outbox messages

Revision ID: e2a71d9f6b40
Revises: d490e19c6832
"""

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision = "e2a71d9f6b40"
down_revision = "d490e19c6832"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outbox_message",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "deduplication_key", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("event_id"),
        sa.UniqueConstraint("deduplication_key"),
    )
    op.create_index(
        op.f("ix_outbox_message_processed_at"), "outbox_message", ["processed_at"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_outbox_message_processed_at"), table_name="outbox_message")
    op.drop_table("outbox_message")
