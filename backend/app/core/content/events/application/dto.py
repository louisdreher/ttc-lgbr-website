from dataclasses import dataclass
from datetime import datetime

from app.core.content.events.domain.event import EventStatus
from app.core.content.types import Visibility


@dataclass(frozen=True, kw_only=True)
class CreateEventCommand:
    title: str
    starts_at: datetime
    category_id: int
    ends_at: datetime | None = None
    is_all_day: bool = False
    status: EventStatus = EventStatus.PLANNED
    visibility: Visibility = Visibility.PUBLIC
    report_expected: bool | None = None
    location: str | None = None
    description: str | None = None
    created_by_user_id: int | None = None


@dataclass(frozen=True, kw_only=True)
class CreateEventCategoryCommand:
    name: str
    slug: str
    default_report_expected: bool = False
    is_active: bool = True
    sort_order: int = 0


@dataclass(frozen=True, kw_only=True)
class UpdateEventCommand:
    event_id: int
    # Presence means supplied; None explicitly clears a nullable field.
    changes: dict


@dataclass(frozen=True, kw_only=True)
class UpdateEventCategoryCommand:
    category_id: int
    changes: dict


@dataclass(frozen=True, kw_only=True)
class DeleteEventCommand:
    event_id: int


@dataclass(frozen=True, kw_only=True)
class DeleteEventsCommand:
    event_ids: list[int]


@dataclass(frozen=True, kw_only=True)
class UpdateEventsVisibilityCommand:
    event_ids: list[int]
    visibility: Visibility


@dataclass(frozen=True, kw_only=True)
class GetEventQuery:
    event_id: int


@dataclass(frozen=True, kw_only=True)
class GetEventsQuery:
    event_ids: list[int]


@dataclass(frozen=True, kw_only=True)
class ListEventsQuery:
    year: int | None = None
    category_ids: list[int] | None = None


@dataclass(frozen=True, kw_only=True)
class ListPublicEventsQuery:
    starts_from: datetime
    starts_until: datetime
    category_ids: list[int] | None = None


@dataclass(frozen=True, kw_only=True)
class EventDetails:
    id: int
    title: str
    starts_at: datetime
    ends_at: datetime | None
    is_all_day: bool
    category_id: int
    team_match_id: int | None
    created_by_user_id: int | None
    status: EventStatus
    visibility: Visibility
    report_expected: bool
    location: str | None
    description: str | None
    created_at: datetime
    updated_at: datetime
    created_by_name: str | None = None


@dataclass(frozen=True, kw_only=True)
class SyncMatchEventCommand:
    """Public input contract: no Competition ORM objects cross into Events."""

    match_id: int
    team_name: str
    opponent_name: str
    is_home: bool
    scheduled_at: datetime
    ended_at: datetime | None
    status: str | None
    is_completed: bool
    venue_name: str | None
    venue_street: str | None
    venue_city: str | None
