from dataclasses import dataclass
from datetime import datetime

from app.core.competition.domain.sync_automation import SyncSettings, SyncState


@dataclass(frozen=True)
class UpdateSyncSettingsCommand:
    settings: SyncSettings


@dataclass(frozen=True)
class AutomationStatus:
    settings: SyncSettings
    state: SyncState
    heartbeat_at: datetime | None
    worker_online: bool
    running: bool
    stale_run: bool
    next_nightly_at: datetime | None
    next_match_at: datetime | None


@dataclass(frozen=True)
class RequestMatchReloadCommand:
    team_match_id: int


@dataclass(frozen=True)
class MatchReloadStatus:
    team_match_id: int
    status: str
    requested_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    last_error: str | None


@dataclass(frozen=True)
class SyncMatchSummary:
    id: int
    team_id: int
    team_name: str
    opponent_name: str
    is_home: bool
    scheduled_at: datetime
    is_completed: bool
    details_imported_at: datetime | None
    reload: MatchReloadStatus | None
    can_reload: bool
    reload_blocked_reason: str | None


@dataclass(frozen=True)
class SyncMatchOverview:
    imported: list[SyncMatchSummary]
    missing_details: list[SyncMatchSummary]
    upcoming: list[SyncMatchSummary]
