from typing import Protocol, Self

from app.core.competition.application.dto import (
    GetScheduleQuery,
    GetTeamStandingsQuery,
    ListTeamsQuery,
    ScheduledMatchSummary,
    StandingSummary,
    TeamSummary,
)
from app.core.competition.domain.teams import RegistrationPosition, Team


class CompetitionRepository(Protocol):
    def get_team(self, team_id: int) -> Team | None: ...
    def registration_for_category(
        self, season_id: int, category: str
    ) -> list[RegistrationPosition]: ...
    def save_team(self, team: Team) -> None: ...


class CompetitionReader(Protocol):
    def get_team_standings(
        self, query: GetTeamStandingsQuery
    ) -> list[StandingSummary]: ...

    def get_schedule(self, query: GetScheduleQuery) -> list[ScheduledMatchSummary]: ...

    def list_teams(self, query: ListTeamsQuery) -> list[TeamSummary]: ...


class PlayerLookup(Protocol):
    def exists(self, player_id: int) -> bool: ...


class CompetitionUnitOfWork(Protocol):
    repository: CompetitionRepository

    def __enter__(self) -> Self: ...
    def __exit__(self, exc_type, exc_value, traceback) -> None: ...
    def commit(self) -> None: ...
