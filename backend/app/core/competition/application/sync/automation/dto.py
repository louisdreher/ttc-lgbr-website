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
