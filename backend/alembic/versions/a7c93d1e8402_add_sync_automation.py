"""Persist myTischtennis scheduling configuration and latest status.

Revision ID: a7c93d1e8402
Revises: f3b82e0a7c51
"""

import sqlalchemy as sa
from alembic import op

revision = "a7c93d1e8402"
down_revision = "f3b82e0a7c51"
branch_labels = None
depends_on = None


def upgrade():
    table = op.create_table(
        "mytt_sync_automation",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("settings", sa.JSON, nullable=False),
        sa.Column("state", sa.JSON, nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("id = 1", name="ck_mytt_sync_singleton"),
    )
    op.bulk_insert(
        table,
        [
            {
                "id": 1,
                "settings": {
                    "enabled": True,
                    "nightly_hour": 3,
                    "nightly_minute": 0,
                    "result_delay_minutes": 180,
                    "result_retry_minutes": 30,
                    "result_retry_window_hours": 24,
                    "include_tables": True,
                    "include_registrations": True,
                },
                "state": {},
            }
        ],
    )
    op.create_table(
        "mytt_match_poll",
        sa.Column(
            "team_match_id",
            sa.Integer,
            sa.ForeignKey("team_match.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("mytt_match_poll")
    op.drop_table("mytt_sync_automation")
