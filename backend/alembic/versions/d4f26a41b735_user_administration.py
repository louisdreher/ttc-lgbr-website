"""Password setup links and immediate session invalidation.

Revision ID: d4f26a41b735
Revises: c9e15f30a624
"""

import sqlalchemy as sa
from alembic import op

revision = "d4f26a41b735"
down_revision = "c9e15f30a624"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "user",
        sa.Column("auth_invalid_before", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "password_link",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), primary_key=True),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_password_link_token_hash", "password_link", ["token_hash"], unique=True
    )


def downgrade():
    op.drop_table("password_link")
    op.drop_column("user", "auth_invalid_before")
