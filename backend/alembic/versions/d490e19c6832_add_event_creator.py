"""add event creator

Revision ID: d490e19c6832
Revises: c38b7a14e921
Create Date: 2026-08-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d490e19c6832"
down_revision: Union[str, Sequence[str], None] = "c38b7a14e921"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("event", sa.Column("created_by_user_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_event_created_by_user_id"), "event", ["created_by_user_id"]
    )
    op.create_foreign_key(
        "fk_event_created_by_user_id_user",
        "event",
        "user",
        ["created_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_event_created_by_user_id_user", "event", type_="foreignkey")
    op.drop_index(op.f("ix_event_created_by_user_id"), table_name="event")
    op.drop_column("event", "created_by_user_id")
