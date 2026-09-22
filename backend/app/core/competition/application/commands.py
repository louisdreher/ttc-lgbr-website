from app.core.competition.application.dto import (
    AssignPlayerToTeamCommand,
    RemovePlayerFromTeamCommand,
)
from app.core.competition.application.errors import (
    PlayerNotFoundError,
    TeamNotFoundError,
)
from app.core.competition.application.ports import (
    CompetitionUnitOfWork,
    PlayerLookup,
)
from app.core.competition.domain.teams import AssignmentRankingError, eligible_registration


class AssignPlayerToTeam:
    def __init__(self, uow: CompetitionUnitOfWork, players: PlayerLookup):

        self.uow = uow
        self.players = players

    def execute(self, command: AssignPlayerToTeamCommand) -> None:
        with self.uow:
            team = self.uow.repository.get_team(command.team_id, for_update=True)

            if team is None:
                raise TeamNotFoundError(command.team_id)

            if not self.players.exists(command.player_id):
                raise PlayerNotFoundError(command.player_id)

            registration = []
            if command.position is None and team.category:
                registration = self.uow.repository.registration_for_category(
                    team.season_id, team.category
                )
                if command.player_id not in eligible_registration(team.team_number, registration):
                    raise AssignmentRankingError(
                        "Der Spieler ist für diese Mannschaft nicht eindeutig oder nicht zulässig gemeldet."
                    )

            team.assign_player(
                player_id=command.player_id,
                registration=registration,
                position=command.position,
                status=command.status,
            )

            self.uow.repository.save_team(team)
            self.uow.commit()


class RemovePlayerFromTeam:
    def __init__(self, uow: CompetitionUnitOfWork):
        self.uow = uow

    def execute(self, command: RemovePlayerFromTeamCommand) -> None:
        with self.uow:
            team = self.uow.repository.get_team(command.team_id, for_update=True)
            if team is None:
                raise TeamNotFoundError(command.team_id)
            if not team.remove_player(command.player_id):
                return
            self.uow.repository.save_team(team)
            self.uow.commit()
