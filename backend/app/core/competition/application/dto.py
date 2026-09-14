from dataclasses import dataclass

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
