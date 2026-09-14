from app.adapters.outbound.competition.events import CompetitionMatchEvents
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
from app.adapters.outbound.persistence.members.player_lookup import SqlPlayerLookup
from app.bootstrap.events import build_sync_match_event
from app.core.competition.application.commands import AssignPlayerToTeam, ListTeams
from sqlmodel import Session


def build_assign_player_to_team(session_factory=None) -> AssignPlayerToTeam:
    session_factory = session_factory or (lambda: Session(engine))
    uow = SqlCompetitionUnitOfWork(
        session_factory,
        SqlCompetitionRepository,
        lambda session: CompetitionMatchEvents(
            session, build_sync_match_event(session)
        ),
        SqlImportedPlayers,
    )
    return AssignPlayerToTeam(uow, SqlPlayerLookup(session_factory))


def build_list_teams(session_factory=None) -> ListTeams:
    session_factory = session_factory or (lambda: Session(engine))

    return ListTeams(reader=SqlCompetitionReader(session_factory))
