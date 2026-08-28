from datetime import datetime, timezone
from enum import StrEnum

import sqlalchemy as sa
from sqlmodel import Field, SQLModel

from app.domains.content.types import Visibility


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EventStatus(StrEnum):
    PLANNED = "PLANNED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    POSTPONED = "POSTPONED"


class EventCategory(SQLModel, table=True):
    __tablename__ = "event_category"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    slug: str = Field(unique=True, index=True)
    default_report_expected: bool = False
    is_active: bool = True
    sort_order: int = Field(default=0, index=True)


class Event(SQLModel, table=True):
    __tablename__ = "event"
    __table_args__ = (
        sa.CheckConstraint(
            "ends_at IS NULL OR ends_at >= starts_at",
            name="ck_event_end_not_before_start",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    title: str
    starts_at: datetime = Field(
        index=True,
        sa_type=sa.DateTime(timezone=True),
    )
    ends_at: datetime | None = Field(
        default=None,
        sa_type=sa.DateTime(timezone=True),
    )
    category_id: int = Field(
        foreign_key="event_category.id",
        index=True,
    )
    team_match_id: int | None = Field(
        default=None,
        foreign_key="team_match.id",
        ondelete="SET NULL",
        unique=True,
        index=True,
    )
    status: EventStatus = Field(
        default=EventStatus.PLANNED,
        sa_type=sa.Enum(EventStatus, name="event_status"),
        index=True,
    )
    visibility: Visibility = Field(
        default=Visibility.PUBLIC,
        sa_type=sa.Enum(Visibility, name="content_visibility"),
        index=True,
    )
    report_expected: bool = Field(default=False, index=True)
    location: str | None = None
    description: str | None = None
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_type=sa.DateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_type=sa.DateTime(timezone=True),
    )
