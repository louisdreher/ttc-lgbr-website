from datetime import datetime, timezone

from app.adapters.outbound.persistence.competition.automation import (
    SqlAutomationUnitOfWork,
)
from app.adapters.outbound.persistence.competition.reader import SqlCompetitionReader
from app.adapters.outbound.persistence.competition.sync_overview import (
    SqlSyncMatchOverviewReader,
)
from app.adapters.outbound.persistence.database import engine
from app.bootstrap.competition_sync import build_competition
from app.core.competition.application.sync.automation.commands import (
    RecordWorkerHeartbeat,
    RequestMatchReload,
    RequestSync,
    RunScheduledSync,
    UpdateSyncSettings,
)
from app.core.competition.application.sync.automation.queries import (
    GetSyncMatches,
    GetSyncStatus,
)
from sqlmodel import Session


def clock():
    return datetime.now(timezone.utc)


def uow():
    return SqlAutomationUnitOfWork(lambda: Session(engine))


def build_get_sync_status():
    return GetSyncStatus(
        lambda: SqlAutomationUnitOfWork(lambda: Session(engine), write=False), clock
    )


def build_update_sync_settings():
    return UpdateSyncSettings(uow)


def build_request_sync():
    return RequestSync(uow)


def build_request_match_reload():
    return RequestMatchReload(uow, clock)


def build_get_sync_matches():
    return GetSyncMatches(SqlSyncMatchOverviewReader(lambda: Session(engine)), clock)


def build_worker_heartbeat():
    return RecordWorkerHeartbeat(uow, clock)


def build_scheduled_sync():
    return RunScheduledSync(
        uow, build_competition(), SqlCompetitionReader(lambda: Session(engine)), clock
    )
