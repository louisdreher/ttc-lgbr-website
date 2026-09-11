import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlmodel import Session

from app.adapters.outbound.competition.events import CompetitionMatchEvents
from app.adapters.outbound.mytischtennis.client import MyTischtennisClient
from app.adapters.outbound.mytischtennis.source import MyTischtennisSource
from app.adapters.outbound.persistence.competition.diagnostics import (
    SqlRegistrationReportReader,
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
from app.adapters.outbound.persistence.members.player_lookup import SqlPlayerLookup
from app.bootstrap.events import build_sync_match_event
from app.bootstrap.settings import settings
from app.core.competition.application.usecases.commands import AssignPlayerToTeam
from app.core.competition.application.usecases.queries import GetRegistrationReport
from app.core.competition.application.usecases.sync.backfill import BackfillMatchEvents
from app.core.competition.application.usecases.sync.batches import (
    ImportBatch,
    SyncCurrent,
    SyncHistory,
)
from app.core.competition.application.usecases.sync.commands import (
    SyncExternalMeeting,
    SyncMeeting,
    SyncRegistrations,
    SyncSchedule,
    SyncStandings,
)


def build_backfill_match_events(session_factory=None):
    return BackfillMatchEvents(
        SqlCompetitionUnitOfWork(
            session_factory or (lambda: Session(engine)),
            SqlCompetitionRepository,
            lambda session: CompetitionMatchEvents(
                session, build_sync_match_event(session)
            ),
            SqlImportedPlayers,
        )
    )


def build_registration_report():
    return GetRegistrationReport(SqlRegistrationReportReader(engine))


def build_mytt_client():
    return MyTischtennisClient(
        base_url=str(settings.mytt_base_url),
        organization=settings.mytt_organization,
        club_number=str(settings.mytt_club_number),
        club_slug=settings.mytt_club_slug,
    )


@dataclass
class CompetitionUseCases:
    schedule: SyncSchedule
    meeting: SyncMeeting
    external_meeting: SyncExternalMeeting
    registrations: SyncRegistrations
    standings: SyncStandings
    current: SyncCurrent
    history: SyncHistory


def build_competition(
    *, session_factory=None, source=None, clock=None, today=None, sleep=None
) -> CompetitionUseCases:
    session_factory = session_factory or (lambda: Session(engine))
    source = source or MyTischtennisSource(
        build_mytt_client(), str(settings.mytt_club_number)
    )
    clock = clock or (lambda: datetime.now(timezone.utc))
    reader = SqlCompetitionReader(session_factory)

    def uow():
        return SqlCompetitionUnitOfWork(
            session_factory,
            SqlCompetitionRepository,
            lambda session: CompetitionMatchEvents(
                session, build_sync_match_event(session)
            ),
            SqlImportedPlayers,
        )

    schedule = SyncSchedule(source, uow())
    meeting = SyncMeeting(source, reader, uow(), clock)
    registrations = SyncRegistrations(source, reader, uow())
    standings = SyncStandings(source, reader, uow())
    batch = ImportBatch(sleep or asyncio.sleep)
    return CompetitionUseCases(
        schedule,
        meeting,
        SyncExternalMeeting(reader, meeting),
        registrations,
        standings,
        SyncCurrent(
            schedule,
            meeting,
            registrations,
            standings,
            reader,
            batch,
            today or date.today,
        ),
        SyncHistory(meeting, registrations, standings, reader, batch, clock),
    )


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
