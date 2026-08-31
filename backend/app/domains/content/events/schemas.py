from datetime import datetime
from typing import Annotated

from app.domains.content.events.model import EventStatus
from app.domains.content.types import Visibility
from pydantic import ConfigDict, StringConstraints
from sqlmodel import Field, SQLModel

Slug = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    ),
]


class EventCategoryCreate(SQLModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    slug: Slug
    default_report_expected: bool = False
    is_active: bool = True
    sort_order: int = 0


class EventCategoryUpdate(SQLModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    slug: Slug | None = None
    default_report_expected: bool | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class EventCategoryRead(SQLModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    default_report_expected: bool
    is_active: bool
    sort_order: int


class PublicEventCategoryRead(SQLModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str


class EventCreate(SQLModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    starts_at: datetime
    ends_at: datetime | None = None
    is_all_day: bool = False
    category_id: int
    status: EventStatus = EventStatus.PLANNED
    visibility: Visibility = Visibility.PUBLIC
    report_expected: bool | None = None
    location: str | None = Field(default=None, max_length=300)
    description: str | None = None


class EventUpdate(SQLModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_all_day: bool | None = None
    category_id: int | None = None
    status: EventStatus | None = None
    visibility: Visibility | None = None
    report_expected: bool | None = None
    location: str | None = Field(default=None, max_length=300)
    description: str | None = None


class EventRead(SQLModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    starts_at: datetime
    ends_at: datetime | None
    is_all_day: bool
    category_id: int
    team_match_id: int | None
    created_by_user_id: int | None
    created_by_name: str | None = None
    status: EventStatus
    visibility: Visibility
    report_expected: bool
    location: str | None
    description: str | None
    created_at: datetime
    updated_at: datetime


class PublicEventRead(SQLModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    starts_at: datetime
    ends_at: datetime | None
    is_all_day: bool
    category_id: int
    status: EventStatus
    location: str | None
    description: str | None


class EventIds(SQLModel):
    model_config = ConfigDict(extra="forbid")
    event_ids: list[int] = Field(min_length=1, max_length=500)


class EventBulkVisibilityUpdate(EventIds):
    visibility: Visibility
