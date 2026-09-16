from datetime import datetime
from typing import Protocol, Self

from app.core.competition.application.sync.commands import (
    SyncMeeting,
    SyncRegistrations,
    SyncSchedule,
    SyncStandings,
)
from app.core.competition.domain.sync_automation import (
    ScheduledMatch,
    SyncSettings,
    SyncState,
)


class AutomationRepository(Protocol):
    def settings(self) -> SyncSettings: ...
    def save_settings(self, settings: SyncSettings) -> None: ...
    def state(self) -> SyncState: ...
    def save_state(self, state: SyncState) -> None: ...
    def heartbeat(self) -> datetime | None: ...
    def save_heartbeat(self, now: datetime) -> None: ...
    def candidates(self, since: datetime) -> list[ScheduledMatch]: ...
    def attempted(self, match: ScheduledMatch, now: datetime) -> None: ...


class AutomationUnitOfWork(Protocol):
    repository: AutomationRepository

    def __enter__(self) -> Self: ...
    def __exit__(self, *args) -> None: ...
    def commit(self) -> None: ...


class ScheduledCompetition(Protocol):
    schedule: SyncSchedule
    meeting: SyncMeeting
    standings: SyncStandings
    registrations: SyncRegistrations
