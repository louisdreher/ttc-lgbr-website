"""Scheduling rules; all instants are UTC, the nightly wall clock is Berlin."""

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo("Europe/Berlin")


@dataclass(frozen=True)
class SyncSettings:
    enabled: bool = True
    nightly_hour: int = 3
    nightly_minute: int = 0
    result_delay_minutes: int = 180
    result_retry_minutes: int = 30
    result_retry_window_hours: int = 24
    include_tables: bool = True
    include_registrations: bool = True

    def __post_init__(self):
        for name in ("enabled", "include_tables", "include_registrations"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} muss ein Wahrheitswert sein.")
        for name, low, high in (
            ("nightly_hour", 0, 23),
            ("nightly_minute", 0, 59),
            ("result_delay_minutes", 0, 1440),
            ("result_retry_minutes", 5, 1440),
            ("result_retry_window_hours", 1, 168),
        ):
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"{name} muss zwischen {low} und {high} liegen.")

    def nightly_slot(self, now: datetime) -> datetime:
        day = now.astimezone(BERLIN).date()
        slot = self._slot(day)
        return self._slot(day - timedelta(days=1)) if slot > now else slot

    def _slot(self, day) -> datetime:
        # A missing spring hour moves forward; an autumn hour uses its first occurrence.
        return datetime.combine(
            day, time(self.nightly_hour, self.nightly_minute), BERLIN
        ).astimezone(timezone.utc)

    def next_nightly(self, now: datetime, last_slot: datetime | None) -> datetime:
        slot = self.nightly_slot(now)
        if last_slot is None or last_slot < slot:
            return now
        today = now.astimezone(BERLIN).date()
        upcoming = self._slot(today)
        return self._slot(today + timedelta(days=1)) if upcoming <= now else upcoming


@dataclass
class SyncRun:
    kind: str
    started_at: datetime
    match_id: int | None = None
    finished_at: datetime | None = None
    status: str = "running"
    imported: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class SyncState:
    requested: bool = False
    last_nightly_slot: datetime | None = None
    last_nightly_success_at: datetime | None = None
    last_run: SyncRun | None = None
    nightly_run: SyncRun | None = None
    last_error: str | None = None
    last_error_at: datetime | None = None


@dataclass(frozen=True)
class ScheduledMatch:
    id: int
    scheduled_at: datetime
    last_attempt_at: datetime | None = None

    def due_at(self, settings: SyncSettings) -> datetime:
        first = self.scheduled_at + timedelta(minutes=settings.result_delay_minutes)
        return (
            max(
                first,
                self.last_attempt_at + timedelta(minutes=settings.result_retry_minutes),
            )
            if self.last_attempt_at
            else first
        )

    def expires_at(self, settings: SyncSettings) -> datetime:
        return self.scheduled_at + timedelta(
            minutes=settings.result_delay_minutes,
            hours=settings.result_retry_window_hours,
        )
