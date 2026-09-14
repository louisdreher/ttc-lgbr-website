from dataclasses import dataclass, field
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


@dataclass(frozen=True)
class GetTeamStandingsQuery:
    team_id: int


@dataclass(frozen=True)
class StandingSummary:
    team_name: str
    position: int
    is_selected_team: bool
    meetings_count: int
    meetings_won: int
    meetings_tie: int
    meetings_lost: int
    points_won: int
    points_lost: int
    matches_won: int
    matches_lost: int
    sets_won: int
    sets_lost: int
    games_won: int
    games_lost: int


@dataclass(frozen=True)
class GetMatchDetailsQuery:
    team_match_id: int


@dataclass(frozen=True)
class MatchPlayer:
    player_id: int
    first_name: str
    last_name: str


@dataclass(frozen=True)
class MatchLineupEntry:
    player: MatchPlayer
    position: int | None
    doubles_pair: int | None


@dataclass(frozen=True)
class MatchSet:
    set_number: int
    points_ttc: int
    points_opponent: int


@dataclass(frozen=True)
class MatchGame:
    id: int
    sequence: int
    game_type: str
    name: str | None
    players: list[MatchPlayer]
    opponent_names: list[str]
    sets: list[MatchSet]


@dataclass(frozen=True)
class MatchNotice:
    code: str
    info: str | None


@dataclass(frozen=True)
class MatchDetails:
    id: int
    team_id: int
    team_name: str
    opponent_name: str
    is_home: bool
    scheduled_at: datetime
    original_scheduled_at: datetime | None
    started_at: datetime | None
    ended_at: datetime | None
    status: str
    is_completed: bool
    score_ttc: int | None
    score_opponent: int | None
    play_mode: str | None
    venue_name: str | None
    venue_street: str | None
    venue_city: str | None
    details_available: bool
    notices: list[MatchNotice] = field(default_factory=list)
    lineup: list[MatchLineupEntry] = field(default_factory=list)
    games: list[MatchGame] = field(default_factory=list)
