from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel
from sqlalchemy import Column, DateTime

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RefreshSession(SQLModel, table=True):
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )

    user_id: int = Field(
        foreign_key="user.id",
        index=True
    )

    token_hash: str = Field(
        unique=True,
        index=True
    )

    family_id: UUID = Field(
        default_factory=uuid4,
        index=True
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False
        )
    )

    expires_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            index=True
        )
    )

    used_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=True
        )
    )

    revoked_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=True
        )
    )