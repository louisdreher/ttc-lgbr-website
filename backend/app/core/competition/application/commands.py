from app.core.competition.application.dto import (
    AssignPlayerToTeamCommand,
    ListTeamsQuery,
    TeamSummary,
)
from app.core.competition.application.errors import (
    PlayerNotFoundError,
    TeamNotFoundError,
)
from app.core.competition.application.ports import (
    CompetitionReader,
    CompetitionUnitOfWork,
    PlayerLookup,
)


class AssignPlayerToTeam:
    def __init__(self, uow: CompetitionUnitOfWork, players: PlayerLookup):

        self.uow = uow
        self.players = players

    def execute(self, command: AssignPlayerToTeamCommand) -> None:
        with self.uow:
            team = self.uow.repository.get_team(command.team_id)

            if team is None:
                raise TeamNotFoundError(command.team_id)

            if not self.players.exists(command.player_id):
                raise PlayerNotFoundError(command.player_id)

            registration = []
            if command.position is None and team.category:
                registration = self.uow.repository.registration_for_category(
                    team.season_id, team.category
                )

            team.assign_player(
                player_id=command.player_id,
                registration=registration,
                position=command.position,
                status=command.status,
            )

            self.uow.repository.save_team(team)
            self.uow.commit()


class ListTeams:
    def __init__(self, reader: CompetitionReader):
        self.reader = reader

    def execute(self, query: ListTeamsQuery) -> list[TeamSummary]:
        return self.reader.list_teams(query)
