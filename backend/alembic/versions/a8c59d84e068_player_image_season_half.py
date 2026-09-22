"""Track player images per season half.

Revision ID: a8c59d84e068
Revises: f6b48c73d957
"""

import sqlalchemy as sa
from alembic import op

revision = "a8c59d84e068"
down_revision = "f6b48c73d957"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("player_image", sa.Column("season_half", sa.String(), nullable=True))
    op.execute("UPDATE player_image SET season_half = 'vr'")
    op.alter_column("player_image", "season_half", existing_type=sa.String(), nullable=False)
    op.drop_constraint("player_image_pkey", "player_image", type_="primary")
    op.create_primary_key(
        "player_image_pkey", "player_image", ["player_id", "season_start_year", "season_half"]
    )
    op.create_check_constraint(
        "ck_player_image_season_half", "player_image", "season_half IN ('vr', 'rr')"
    )


def downgrade():
    # A return-round image cannot be represented faithfully by the old schema.
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM player_image WHERE season_half = 'rr')"
    )).scalar():
        raise RuntimeError("Downgrade blocked: return-round player images must be resolved explicitly.")
    op.drop_constraint("ck_player_image_season_half", "player_image", type_="check")
    op.drop_constraint("player_image_pkey", "player_image", type_="primary")
    op.create_primary_key("player_image_pkey", "player_image", ["player_id", "season_start_year"])
    op.drop_column("player_image", "season_half")
