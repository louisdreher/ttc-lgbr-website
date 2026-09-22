"""Add player images by full season.

Revision ID: f6b48c73d957
Revises: e5a37b62c846
"""

import sqlalchemy as sa
from alembic import op

revision = "f6b48c73d957"
down_revision = "e5a37b62c846"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "player_image",
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("season_start_year", sa.Integer(), nullable=False),
        sa.Column("media_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["player_id"], ["player.id"]),
        sa.ForeignKeyConstraint(["media_id"], ["media_asset.id"]),
        sa.PrimaryKeyConstraint("player_id", "season_start_year"),
    )


def downgrade():
    op.drop_table("player_image")
