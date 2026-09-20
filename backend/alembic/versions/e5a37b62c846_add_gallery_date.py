"""Add independent gallery dates and display preference.

Revision ID: e5a37b62c846
Revises: d4f26a41b735
"""

import sqlalchemy as sa
from alembic import op

revision = "e5a37b62c846"
down_revision = "d4f26a41b735"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("gallery", sa.Column("gallery_date", sa.Date(), nullable=True))
    op.add_column("gallery", sa.Column("show_date", sa.Boolean(), nullable=True))
    # Club-local calendar dates, independent of the database session timezone.
    # Standalone legacy galleries have no factual date; hide the fallback date.
    op.execute(sa.text("""
        UPDATE gallery AS g
        SET gallery_date = COALESCE(
                (SELECT (e.starts_at AT TIME ZONE 'Europe/Berlin')::date
                 FROM event AS e WHERE e.id = g.event_id),
                (g.created_at AT TIME ZONE 'Europe/Berlin')::date
            ),
            show_date = (g.event_id IS NOT NULL)
    """))
    op.alter_column("gallery", "gallery_date", existing_type=sa.Date(), nullable=False)
    op.alter_column("gallery", "show_date", existing_type=sa.Boolean(), nullable=False)
    op.create_index("ix_gallery_gallery_date", "gallery", ["gallery_date"])


def downgrade():
    op.drop_index("ix_gallery_gallery_date", table_name="gallery")
    op.drop_column("gallery", "show_date")
    op.drop_column("gallery", "gallery_date")
