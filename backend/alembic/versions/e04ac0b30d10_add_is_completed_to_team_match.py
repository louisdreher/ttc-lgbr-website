"""add is_completed to team_match

Revision ID: e04ac0b30d10
Revises: bfa66fc8f888
Create Date: 2026-08-27 04:35:24.200962

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e04ac0b30d10"
down_revision: Union[str, Sequence[str], None] = "bfa66fc8f888"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.add_column(
        "team_match",
        sa.Column(
            "is_completed",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )

    op.create_index(
        op.f("ix_team_match_is_completed"),
        "team_match",
        ["is_completed"],
        unique=False,
    )

    # Default nur für die Migration benötigt.
    # Danach soll der Default aus dem Python-Modell kommen.
    op.alter_column(
        "team_match",
        "is_completed",
        server_default=None,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(
        op.f("ix_team_match_is_completed"),
        table_name="team_match",
    )

    op.drop_column(
        "team_match",
        "is_completed",
    )
