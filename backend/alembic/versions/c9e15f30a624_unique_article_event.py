"""Enforce one article per event without deleting existing content.

Revision ID: c9e15f30a624
Revises: b8d04e2f9513
"""

import sqlalchemy as sa
from alembic import op

revision = "c9e15f30a624"
down_revision = "b8d04e2f9513"
branch_labels = None
depends_on = None


def upgrade():
    duplicate = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT event_id FROM article WHERE event_id IS NOT NULL "
                "GROUP BY event_id HAVING COUNT(*) > 1 LIMIT 1"
            )
        )
        .first()
    )
    if duplicate:
        raise RuntimeError(
            "Mehrere Artikel für einen Event vorhanden; "
            "Zuordnung vor der Migration klären."
        )
    op.create_unique_constraint("uq_article_event_id", "article", ["event_id"])


def downgrade():
    op.drop_constraint("uq_article_event_id", "article", type_="unique")
