"""add report provenance, system author and outbox delivery state

Revision ID: f3b82e0a7c51
Revises: e2a71d9f6b40
"""

from datetime import datetime, timezone
from uuid import uuid4

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision = "f3b82e0a7c51"
down_revision = "e2a71d9f6b40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    string = sqlmodel.sql.sqltypes.AutoString
    op.add_column("user", sa.Column("system_key", string(), nullable=True))
    op.create_unique_constraint("uq_user_system_key", "user", ["system_key"])
    op.add_column("article", sa.Column("generation_key", string(), nullable=True))
    op.create_unique_constraint(
        "uq_article_generation_key", "article", ["generation_key"]
    )
    op.add_column("article", sa.Column("generation_method", string(), nullable=True))
    op.add_column(
        "article", sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "outbox_message",
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("outbox_message", "attempts", server_default=None)
    for name in ("next_attempt_at", "locked_until", "failed_at"):
        op.add_column(
            "outbox_message", sa.Column(name, sa.DateTime(timezone=True), nullable=True)
        )
    op.add_column("outbox_message", sa.Column("lock_token", sa.Uuid(), nullable=True))
    op.add_column("outbox_message", sa.Column("last_error", string(), nullable=True))
    users = sa.table(
        "user",
        sa.column("email", sa.String()),
        sa.column("name", sa.String()),
        sa.column("password_hash", sa.String()),
        sa.column("is_active", sa.Boolean()),
        sa.column("created_at", sa.DateTime()),
        sa.column("system_key", sa.String()),
    )
    # No password or login credential is created. Existing users are never repurposed.
    op.bulk_insert(
        users,
        [
            {
                "email": f"system-articles-{uuid4().hex}@internal.invalid",
                "name": "System",
                "password_hash": "!",
                "is_active": False,
                "created_at": datetime.now(timezone.utc).replace(tzinfo=None),
                "system_key": "article-automation",
            }
        ],
    )


def downgrade() -> None:
    # Keep the inactive system user: existing articles may still reference its ID.
    for name in (
        "last_error",
        "lock_token",
        "failed_at",
        "locked_until",
        "next_attempt_at",
        "attempts",
    ):
        op.drop_column("outbox_message", name)
    op.drop_column("article", "generated_at")
    op.drop_column("article", "generation_method")
    op.drop_constraint("uq_article_generation_key", "article", type_="unique")
    op.drop_column("article", "generation_key")
    op.drop_constraint("uq_user_system_key", "user", type_="unique")
    op.drop_column("user", "system_key")
