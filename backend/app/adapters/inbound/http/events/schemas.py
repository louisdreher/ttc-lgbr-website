from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.content.events.domain.event import EventStatus
from app.core.content.types import Visibility

Slug = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    ),
]


class EventCategoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    slug: Slug
    default_report_expected: bool = False
    is_active: bool = True
    sort_order: int = 0


class EventCategoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    slug: Slug | None = None
    default_report_expected: bool | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class EventCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    default_report_expected: bool
    is_active: bool
    sort_order: int


class PublicEventCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str


class EventCreate(BaseModel):
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


class EventUpdate(BaseModel):
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


class EventRead(BaseModel):
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


class PublicEventRead(BaseModel):
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


class EventIds(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_ids: list[int] = Field(min_length=1, max_length=500)


class EventBulkVisibilityUpdate(EventIds):
    visibility: Visibility
