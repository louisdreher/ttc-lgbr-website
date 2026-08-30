"""add event all-day flag

Revision ID: c38b7a14e921
Revises: 7db6ed6f7c03
Create Date: 2026-08-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c38b7a14e921"
down_revision: Union[str, Sequence[str], None] = "7db6ed6f7c03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "event",
        sa.Column(
            "is_all_day", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.create_index(op.f("ix_event_is_all_day"), "event", ["is_all_day"])
    op.alter_column("event", "is_all_day", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_event_is_all_day"), table_name="event")
    op.drop_column("event", "is_all_day")
