from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class OutboxMessage(SQLModel, table=True):
    """A durable message written in the same transaction as its source change."""

    __tablename__ = "outbox_message"

    event_id: UUID = Field(primary_key=True)
    event_type: str
    deduplication_key: str = Field(unique=True)
    occurred_at: datetime = Field(sa_type=sa.DateTime(timezone=True))
    payload: dict = Field(sa_column=sa.Column(sa.JSON(), nullable=False))
    processed_at: datetime | None = Field(
        default=None, sa_type=sa.DateTime(timezone=True), index=True
    )
    attempts: int = 0
    next_attempt_at: datetime | None = Field(
        default=None, sa_type=sa.DateTime(timezone=True)
    )
    locked_until: datetime | None = Field(
        default=None, sa_type=sa.DateTime(timezone=True)
    )
    lock_token: UUID | None = None
    failed_at: datetime | None = Field(default=None, sa_type=sa.DateTime(timezone=True))
    last_error: str | None = None
