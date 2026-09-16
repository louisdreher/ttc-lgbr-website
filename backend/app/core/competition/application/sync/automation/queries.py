from collections.abc import Callable
from datetime import datetime, timedelta

from app.core.competition.application.sync.automation.dto import (
    AutomationStatus,
    SyncMatchOverview,
)
from app.core.competition.application.sync.automation.ports import (
    AutomationUnitOfWork,
    SyncMatchOverviewReader,
)


class GetSyncMatches:
    def __init__(self, reader: SyncMatchOverviewReader, clock: Callable[[], datetime]):
        self.reader, self.clock = reader, clock

    def execute(self) -> SyncMatchOverview:
        return self.reader.read(self.clock())


class GetSyncStatus:
    def __init__(
        self,
        uow_factory: Callable[[], AutomationUnitOfWork],
        clock: Callable[[], datetime],
    ):
        self.uow_factory, self.clock = uow_factory, clock

    def execute(self) -> AutomationStatus:
        now = self.clock()
        with self.uow_factory() as uow:
            repo = uow.repository
            settings, state, heartbeat = repo.settings(), repo.state(), repo.heartbeat()
            candidates = repo.candidates(
                now
                - timedelta(
                    minutes=settings.result_delay_minutes,
                    hours=settings.result_retry_window_hours,
                )
            )
        due = [
            max(now, m.due_at(settings))
            for m in candidates
            if max(now, m.due_at(settings)) <= m.expires_at(settings)
        ]
        online = heartbeat is not None and now - heartbeat <= timedelta(seconds=90)
        unfinished = state.last_run is not None and state.last_run.status == "running"
        return AutomationStatus(
            settings,
            state,
            heartbeat,
            online,
            unfinished and online,
            unfinished and not online,
            settings.next_nightly(now, state.last_nightly_slot)
            if settings.enabled
            else None,
            min(due, default=None) if settings.enabled else None,
        )
