from dataclasses import dataclass, field

from app.core.competition.domain.imports import SeasonKey


@dataclass(frozen=True)
class BackfillMatchEventsCommand:
    completed_only: bool = False


@dataclass(frozen=True)
class SyncScheduleCommand:
    season: SeasonKey


@dataclass(frozen=True)
class SyncMeetingCommand:
    team_match_id: int
    force: bool = False


@dataclass(frozen=True)
class SyncExternalMeetingCommand:
    external_id: int
    force: bool = False


@dataclass(frozen=True)
class SyncGroupCommand:
    league_group_id: int
    skip_existing: bool = False


@dataclass(frozen=True)
class SyncCurrentCommand:
    kind: str


@dataclass(frozen=True)
class SyncHistoryCommand:
    kind: str
    start_year: int | None = None
    end_year: int | None = None
    skip_existing: bool = True


@dataclass
class ImportSummary:
    imported: int = 0
    skipped: int = 0
    failed: list[int] = field(default_factory=list)
