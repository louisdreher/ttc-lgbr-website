from dataclasses import dataclass
from datetime import date, datetime

from app.core.competition.domain.teams import AssignmentStatus


@dataclass(frozen=True)
class AssignPlayerToTeamCommand:
    team_id: int
    player_id: int
    status: AssignmentStatus | None = None
    position: int | None = None


@dataclass(frozen=True)
class ListTeamsQuery:
    season_id: int
    category: str | None = None


@dataclass(frozen=True)
class TeamSummary:
    id: int
    name: str
    team_number: int | None
    category: str | None


@dataclass(frozen=True)
class GetScheduleQuery:
    date_from: date
    date_to: date
    team_ids: tuple[int, ...] | None = None
    category: str | None = None


@dataclass(frozen=True)
class ScheduledMatchSummary:
    id: int
    team_id: int
    team_name: str
    opponent_name: str
    is_home: bool
    scheduled_at: datetime
    status: str
    is_completed: bool
    score_ttc: int | None
    score_opponent: int | None
