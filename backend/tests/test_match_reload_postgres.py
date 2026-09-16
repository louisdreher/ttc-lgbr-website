import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier, Event
from unittest.mock import Mock

from alembic import command
from app.adapters.inbound.cli.content_worker import ContentWorker
from app.adapters.outbound.persistence.competition.automation import (
    MatchReloadRequest,
    SqlAutomationUnitOfWork,
)
from app.adapters.outbound.persistence.competition.matches import TeamMatch
from app.adapters.outbound.persistence.competition.reader import SqlCompetitionReader
from app.adapters.outbound.persistence.competition.worker_lock import (
    SqlCompetitionWorkerLock,
)
from app.adapters.outbound.persistence.messaging.models import OutboxMessage
from app.bootstrap.competition_sync import build_competition
from app.core.competition.application.sync.automation.commands import (
    RequestMatchReload,
    RunScheduledSync,
)
from app.core.competition.application.sync.automation.dto import (
    RequestMatchReloadCommand,
)
from app.core.competition.application.sync.imports import MeetingDetails
from app.core.competition.domain.sync_automation import SyncSettings
from app.core.messaging.application.dto import ProcessingSummary
from sqlalchemy import delete, inspect
from sqlmodel import Session, select
from test_outbox_postgres import postgres_database, seed_report_match  # noqa: F401


def make_pending(engine, match_id):
    with Session(engine) as session:
        session.get(TeamMatch, match_id).details_imported_at = None
        session.commit()


def test_reload_migration_upgrade_preserves_data_and_cascades_only_job(
    postgres_database,  # noqa: F811 -- shared disposable database fixture
):
    engine, config = postgres_database
    command.upgrade(config, "a7c93d1e8402")
    match_id = seed_report_match(engine)
    command.upgrade(config, "head")
    command.check(config)
    with Session(engine) as session:
        assert session.get(TeamMatch, match_id).details_imported_at is not None
        assert session.exec(select(MatchReloadRequest)).all() == []
    make_pending(engine, match_id)
    uow = lambda: SqlAutomationUnitOfWork(lambda: Session(engine))
    RequestMatchReload(uow, lambda: datetime.now(timezone.utc)).execute(
        RequestMatchReloadCommand(match_id)
    )
    with Session(engine) as session:
        session.execute(delete(TeamMatch).where(TeamMatch.id == match_id))
        session.commit()
        assert session.exec(select(MatchReloadRequest)).all() == []
    command.downgrade(config, "a7c93d1e8402")
    assert "mytt_match_reload" not in inspect(engine).get_table_names()
    command.upgrade(config, "head")
    command.check(config)


def test_parallel_enqueue_and_workers_use_one_manual_import(postgres_database):  # noqa: F811
    engine, config = postgres_database
    command.upgrade(config, "head")  # complete chain from an empty database
    command.check(config)
    match_id = seed_report_match(engine)
    make_pending(engine, match_id)
    uow = lambda: SqlAutomationUnitOfWork(lambda: Session(engine))
    clock = lambda: datetime.now(timezone.utc)
    request = RequestMatchReload(uow, clock)
    barrier = Barrier(2)

    def enqueue():
        barrier.wait(timeout=10)
        return request.execute(RequestMatchReloadCommand(match_id))

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(enqueue) for _ in range(2)]
        results = [future.result(timeout=20) for future in futures]
    assert results[0] == results[1]
    with Session(engine) as session:
        assert len(session.exec(select(MatchReloadRequest)).all()) == 1
    with uow() as unit:
        unit.repository.save_settings(SyncSettings(enabled=False))
        unit.commit()
    entered, release = Event(), Event()
    calls = []

    class Source:
        async def meeting(self, external_id):
            calls.append(external_id)
            entered.set()
            assert await asyncio.to_thread(release.wait, 10)
            return MeetingDetails(completed=True, score_home=7, score_away=3, games=())

    def worker():
        competition = build_competition(
            session_factory=lambda: Session(engine), source=Source(), clock=clock
        )
        scheduler = RunScheduledSync(
            uow, competition, SqlCompetitionReader(lambda: Session(engine)), clock
        )
        return ContentWorker(
            scheduler.execute,
            Mock(return_value=ProcessingSummary()),
            SqlCompetitionWorkerLock(engine),
            sync_interval=15,
            poll_interval=10,
        )

    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(lambda: asyncio.run(worker().once()))
        try:
            assert entered.wait(timeout=10)
            assert (
                request.execute(RequestMatchReloadCommand(match_id)).status == "running"
            )
            assert asyncio.run(
                worker().once()
            )  # cannot acquire the first worker's lock
        finally:
            release.set()
        assert first.result(timeout=20)
    assert len(calls) == 1
    with Session(engine) as session:
        assert session.get(MatchReloadRequest, match_id).status == "succeeded"
        assert session.get(TeamMatch, match_id).details_imported_at is not None
        assert (
            session.exec(select(OutboxMessage)).one().payload["import_origin"]
            == "MANUAL"
        )
