"""Persist the latest manual detail reload request per match.

Revision ID: b8d04e2f9513
Revises: a7c93d1e8402
"""

import sqlalchemy as sa
from alembic import op

revision = "b8d04e2f9513"
down_revision = "a7c93d1e8402"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mytt_match_reload",
        sa.Column(
            "team_match_id",
            sa.Integer,
            sa.ForeignKey("team_match.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String),
        sa.CheckConstraint(
            "status IN ('requested', 'running', 'succeeded', 'failed')",
            name="ck_mytt_match_reload_status",
        ),
    )
    op.create_index(
        "ix_mytt_match_reload_queue",
        "mytt_match_reload",
        ["status", "requested_at", "team_match_id"],
    )


def downgrade():
    op.drop_table("mytt_match_reload")
