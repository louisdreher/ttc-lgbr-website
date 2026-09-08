from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum

from app.core.content.events.domain.errors import (
    EventServiceError,
    SyncedEventDeleteError,
    SyncedEventFieldError,
)
from app.core.content.types import Visibility


class EventStatus(StrEnum):
    PLANNED = "PLANNED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    POSTPONED = "POSTPONED"


SYNCED_EVENT_FIELDS = {
    "title",
    "starts_at",
    "ends_at",
    "is_all_day",
    "category_id",
    "status",
    "location",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def required_text(value: str, label: str) -> str:
    value = value.strip()
    if not value:
        raise EventServiceError(f"{label} darf nicht leer sein.")
    return value


def validate_period(starts_at: datetime, ends_at: datetime | None) -> None:
    if starts_at.utcoffset() is None:
        raise EventServiceError("Der Beginn muss eine Zeitzone enthalten.")
    if ends_at is not None and ends_at.utcoffset() is None:
        raise EventServiceError("Das Ende muss eine Zeitzone enthalten.")
    if ends_at is not None and ends_at < starts_at:
        raise EventServiceError(
            "Das Ende eines Events darf nicht vor seinem Beginn liegen."
        )


def reject_nulls(changes: dict, required: set[str]) -> None:
    nulls = sorted(key for key in required if key in changes and changes[key] is None)
    if nulls:
        raise EventServiceError(
            f"Diese Felder dürfen nicht null sein: {', '.join(nulls)}."
        )


@dataclass(kw_only=True)
class Event:
    title: str
    starts_at: datetime
    category_id: int
    id: int | None = None
    ends_at: datetime | None = None
    is_all_day: bool = False
    team_match_id: int | None = None
    created_by_user_id: int | None = None
    status: EventStatus = EventStatus.PLANNED
    visibility: Visibility = Visibility.PUBLIC
    report_expected: bool = False
    location: str | None = None
    description: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @classmethod
    def create(cls, **values) -> "Event":
        event = cls(**values)
        event.title = required_text(event.title, "Der Event-Titel")
        validate_period(event.starts_at, event.ends_at)
        return event

    def edit(self, changes: dict) -> None:
        changes = dict(changes)
        allowed = SYNCED_EVENT_FIELDS | {"visibility", "report_expected", "description"}
        if set(changes) - allowed:
            raise EventServiceError("Unbekannte Event-Felder.")
        reject_nulls(
            changes,
            {
                "title",
                "starts_at",
                "is_all_day",
                "category_id",
                "status",
                "visibility",
                "report_expected",
            },
        )
        if self.team_match_id is not None:
            protected = SYNCED_EVENT_FIELDS.intersection(changes)
            if protected:
                raise SyncedEventFieldError(
                    "Synchronisierte Event-Felder können nicht geändert werden: "
                    f"{', '.join(sorted(protected))}."
                )
        if "title" in changes:
            changes["title"] = required_text(changes["title"], "Der Event-Titel")
        if "starts_at" in changes or "ends_at" in changes:
            validate_period(
                changes.get("starts_at", self.starts_at),
                changes.get("ends_at", self.ends_at),
            )
        for name, value in changes.items():
            setattr(self, name, value)
        self.updated_at = utc_now()

    def ensure_deletable(self) -> None:
        if self.team_match_id is not None:
            raise SyncedEventDeleteError(
                "Synchronisierte Mannschaftsspiele können nicht gelöscht werden."
            )

    def change_visibility(self, visibility: Visibility, *, now: datetime) -> None:
        self.visibility = visibility
        self.updated_at = now

    def synchronize(
        self,
        *,
        title: str,
        starts_at: datetime,
        ends_at: datetime | None,
        category_id: int,
        status: EventStatus,
        location: str | None,
    ) -> None:
        """Only the owning match import can replace these fields."""
        self.title = required_text(title, "Der Event-Titel")
        validate_period(starts_at, ends_at)
        self.starts_at = starts_at
        self.ends_at = ends_at
        self.is_all_day = False
        self.category_id = category_id
        self.status = status
        self.location = location
        self.updated_at = utc_now()
