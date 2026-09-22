from app.adapters.outbound.competition.events import CompetitionMatchEvents
from app.adapters.outbound.persistence.competition.outbox import (
    SqlCompetitionEventOutbox,
)
from app.adapters.outbound.persistence.competition.reader import SqlCompetitionReader
from app.adapters.outbound.persistence.competition.repository import (
    SqlCompetitionRepository,
)
from app.adapters.outbound.persistence.competition.unit_of_work import (
    SqlCompetitionUnitOfWork,
)
from app.adapters.outbound.persistence.database import engine
from app.adapters.outbound.persistence.members.imported_players import (
    SqlImportedPlayers,
)
from app.adapters.outbound.persistence.members.match_players import SqlMatchPlayerReader
from app.adapters.outbound.persistence.members.player_lookup import SqlPlayerLookup
from app.bootstrap.events import build_sync_match_event
from app.bootstrap.members import build_get_player_images
from app.core.competition.application.commands import (
    AssignPlayerToTeam,
    RemovePlayerFromTeam,
)
from app.core.competition.application.queries import (
    GetTeamCandidates,
    GetMatchDetails,
    GetSchedule,
    GetTeamLineup,
    GetTeamStandings,
    ListSeasons,
    ListTeams,
)
from sqlmodel import Session


def build_get_team_candidates(session_factory=None) -> GetTeamCandidates:
    session_factory = session_factory or (lambda: Session(engine))
    return GetTeamCandidates(SqlCompetitionReader(session_factory, SqlMatchPlayerReader(session_factory)))


def build_assign_player_to_team(session_factory=None) -> AssignPlayerToTeam:
    session_factory = session_factory or (lambda: Session(engine))
    uow = SqlCompetitionUnitOfWork(
        session_factory,
        SqlCompetitionRepository,
        lambda session: CompetitionMatchEvents(
            session, build_sync_match_event(session)
        ),
        SqlImportedPlayers,
        SqlCompetitionEventOutbox,
    )
    return AssignPlayerToTeam(uow, SqlPlayerLookup(session_factory))


def build_list_teams(session_factory=None) -> ListTeams:
    session_factory = session_factory or (lambda: Session(engine))

    return ListTeams(reader=SqlCompetitionReader(session_factory))


def build_get_schedule(session_factory=None) -> GetSchedule:
    session_factory = session_factory or (lambda: Session(engine))
    return GetSchedule(SqlCompetitionReader(session_factory))


def build_get_team_standings(session_factory=None) -> GetTeamStandings:
    session_factory = session_factory or (lambda: Session(engine))
    return GetTeamStandings(SqlCompetitionReader(session_factory))


def build_get_match_details(session_factory=None) -> GetMatchDetails:
    session_factory = session_factory or (lambda: Session(engine))
    return GetMatchDetails(
        SqlCompetitionReader(session_factory, SqlMatchPlayerReader(session_factory))
    )


def build_get_team_lineup(session_factory=None) -> GetTeamLineup:
    session_factory = session_factory or (lambda: Session(engine))
    return GetTeamLineup(
        SqlCompetitionReader(session_factory, SqlMatchPlayerReader(session_factory)),
        build_get_player_images(session_factory),
    )


def build_remove_player_from_team(session_factory=None) -> RemovePlayerFromTeam:
    session_factory = session_factory or (lambda: Session(engine))
    return RemovePlayerFromTeam(
        SqlCompetitionUnitOfWork(
            session_factory,
            SqlCompetitionRepository,
            lambda session: CompetitionMatchEvents(
                session, build_sync_match_event(session)
            ),
            SqlImportedPlayers,
            SqlCompetitionEventOutbox,
        )
    )


def build_list_seasons(session_factory=None) -> ListSeasons:
    session_factory = session_factory or (lambda: Session(engine))
    return ListSeasons(SqlCompetitionReader(session_factory))
