"""Opt-in checks against disposable PostgreSQL databases, never the app database.

Set TTC_TEST_POSTGRES_URL to an administrative connection URL with CREATEDB.
Each test creates and drops only its own randomly named ttc_outbox_test_* database.
"""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from app.adapters.outbound.persistence import database
from app.adapters.outbound.persistence.competition.leagues import LeagueGroup
from app.adapters.outbound.persistence.competition.matches import TeamMatch
from app.adapters.outbound.persistence.competition.outbox import (
    SqlCompetitionEventOutbox,
)
from app.adapters.outbound.persistence.competition.seasons import Season, SeasonHalf
from app.adapters.outbound.persistence.competition.teams import Team
from app.adapters.outbound.persistence.messaging.models import OutboxMessage
from app.bootstrap.competition_sync import build_competition
from app.core.competition.application.events import (
    ImportOrigin,
    TeamMatchResultsImported,
)
from app.core.competition.application.sync.dto import SyncMeetingCommand
from app.core.competition.application.sync.imports import MeetingDetails
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select


def seed_report_match(engine):
    from app.adapters.outbound.competition.events import CompetitionMatchEvents
    from app.bootstrap.events import build_sync_match_event

    with Session(engine) as session:
        season = Season(start_year=2026, end_year=2027, half=SeasonHalf.VR)
        session.add(season)
        session.flush()
        group = LeagueGroup(season_id=season.id, name="Liga", mytt_group_id=1)
        session.add(group)
        session.flush()
        team = Team(
            season_id=season.id, league_group_id=group.id, mytt_team_id=1, name="TTC"
        )
        session.add(team)
        session.flush()
        match = TeamMatch(
            team_id=team.id,
            mytt_meeting_id=321,
            opponent_name="Gast",
            is_home=True,
            scheduled_at=datetime(2026, 9, 15, tzinfo=timezone.utc),
            status="completed",
            is_completed=True,
            details_imported_at=datetime.now(timezone.utc),
            score_ttc=7,
            score_opponent=3,
        )
        session.add(match)
        session.flush()
        match_id = match.id
        CompetitionMatchEvents(session, build_sync_match_event(session)).synchronize(
            match_id
        )
        session.commit()
        return match_id


def test_parallel_report_requests_create_one_draft(postgres_database):
    from app.adapters.outbound.articles.template import PlainTextMatchReportGenerator
    from app.adapters.outbound.persistence.articles.models import Article
    from app.bootstrap.articles import build_create_match_report_draft
    from app.core.content.articles.application.dto import CreateMatchReportDraftCommand

    engine, config = postgres_database
    command.upgrade(config, "head")
    match_id = seed_report_match(engine)
    barrier = Barrier(2)

    class Generator(PlainTextMatchReportGenerator):
        def generate(self, data):
            result = super().generate(data)
            barrier.wait(timeout=10)
            return result

    def generate():
        with Session(engine) as session:
            return build_create_match_report_draft(
                session, generator=Generator()
            ).execute(CreateMatchReportDraftCommand(match_id))

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(generate) for _ in range(2)]
        results = [future.result(timeout=20) for future in futures]
    assert sum(result.created for result in results) == 1
    assert results[0].article_id == results[1].article_id
    with Session(engine) as session:
        assert len(session.exec(select(Article)).all()) == 1


def test_parallel_outbox_claims_have_distinct_messages(postgres_database):
    from datetime import timedelta

    from app.adapters.outbound.persistence.messaging.store import SqlOutboxStore

    engine, config = postgres_database
    command.upgrade(config, "head")
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        for match_id in (1, 2):
            SqlCompetitionEventOutbox(session).add(
                TeamMatchResultsImported(uuid4(), match_id, now, ImportOrigin.CURRENT)
            )
        session.commit()
    store = SqlOutboxStore(lambda: Session(engine))
    barrier = Barrier(2)

    def claim():
        barrier.wait(timeout=10)
        return store.claim(now, timedelta(seconds=30), 5)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(claim) for _ in range(2)]
        deliveries = [future.result(timeout=20) for future in futures]
    assert all(deliveries)
    assert deliveries[0].event_id != deliveries[1].event_id
    assert store.claim(now, timedelta(seconds=30), 5) is None


def test_automation_upgrade_preserves_pending_messages(postgres_database):
    import json

    from app.adapters.outbound.persistence.users.models import User

    engine, config = postgres_database
    command.upgrade(config, "e2a71d9f6b40")
    event_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO outbox_message "
                "(event_id, event_type, deduplication_key, occurred_at, payload) "
                "VALUES (:id, :type, :key, :now, CAST(:payload AS JSON))"
            ),
            {
                "id": event_id,
                "type": "competition.team_match_results_imported.v1",
                "key": "old-message",
                "now": datetime.now(timezone.utc),
                "payload": json.dumps({"team_match_id": 1, "import_origin": "HISTORY"}),
            },
        )
    command.upgrade(config, "head")
    command.check(config)
    with Session(engine) as session:
        message = session.exec(select(OutboxMessage)).one()
        assert message.event_id == event_id and message.attempts == 0
        assert message.failed_at is None and message.processed_at is None
        system = session.exec(
            select(User).where(User.system_key == "article-automation")
        ).one()
        assert (
            not system.is_active and system.password_hash == "!" and system.roles == []
        )


@pytest.fixture
def postgres_database(monkeypatch):
    connection_url = os.environ.get("TTC_TEST_POSTGRES_URL")
    if not connection_url:
        pytest.skip(
            "TTC_TEST_POSTGRES_URL is not set; requires disposable PostgreSQL DBs"
        )
    # Alembic's fileConfig otherwise disables application loggers globally and
    # breaks later caplog tests. Keep pytest's logging configuration in test DBs.
    monkeypatch.setattr("logging.config.fileConfig", lambda *args, **kwargs: None)
    url = make_url(connection_url)
    if url.get_backend_name() != "postgresql":
        pytest.fail("TTC_TEST_POSTGRES_URL must refer to PostgreSQL")
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    name = f"ttc_outbox_test_{uuid4().hex}"
    engine = None
    created = False
    try:
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
        created = True
        engine = create_engine(
            url.set(database=name),
            connect_args={"options": "-c lock_timeout=5000 -c statement_timeout=15000"},
        )
        # alembic/env.py imports this engine; no application configuration changes.
        monkeypatch.setattr(database, "engine", engine)
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        yield engine, config
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with admin.connect() as connection:
                connection.execute(text(f'DROP DATABASE "{name}"'))
        admin.dispose()


def test_outbox_migration_on_empty_postgres(postgres_database):
    engine, config = postgres_database
    command.upgrade(config, "head")
    command.check(config)
    event = TeamMatchResultsImported(
        event_id=uuid4(),
        team_match_id=123,
        occurred_at=datetime(2026, 9, 15, tzinfo=timezone.utc),
        import_origin=ImportOrigin.HISTORY,
    )
    with Session(engine) as session:
        SqlCompetitionEventOutbox(session).add(event)
        session.commit()
    with Session(engine) as session:
        message = session.exec(select(OutboxMessage)).one()
        assert message.event_id == event.event_id
        assert message.occurred_at == event.occurred_at
        assert message.payload == {"team_match_id": 123, "import_origin": "HISTORY"}
        assert message.processed_at is None
        duplicate = TeamMatchResultsImported(
            event_id=uuid4(),
            team_match_id=123,
            occurred_at=event.occurred_at,
            import_origin=ImportOrigin.CURRENT,
        )
        with pytest.raises(IntegrityError):
            SqlCompetitionEventOutbox(session).add(duplicate)
        session.rollback()
        assert session.exec(select(OutboxMessage)).one().event_id == event.event_id


def test_sync_automation_upgrade_and_parallel_control(postgres_database):
    from app.adapters.outbound.persistence.competition.automation import (
        SqlAutomationUnitOfWork,
        SyncAutomation,
    )
    from app.adapters.outbound.persistence.competition.worker_lock import (
        SqlCompetitionWorkerLock,
    )
    from app.core.competition.application.sync.automation.commands import (
        RecordWorkerHeartbeat,
        RequestSync,
        UpdateSyncSettings,
    )
    from app.core.competition.application.sync.automation.dto import (
        UpdateSyncSettingsCommand,
    )
    from app.core.competition.domain.sync_automation import SyncSettings

    engine, config = postgres_database
    command.upgrade(config, "f3b82e0a7c51")
    match_id = seed_report_match(engine)
    command.upgrade(config, "head")
    command.check(config)
    uow = lambda: SqlAutomationUnitOfWork(lambda: Session(engine))
    now = datetime.now(timezone.utc)
    barrier = Barrier(3)

    def execute(operation):
        barrier.wait(timeout=10)
        operation()

    with ThreadPoolExecutor(max_workers=3) as pool:
        operations = [
            lambda: RequestSync(uow).execute(),
            lambda: RecordWorkerHeartbeat(uow, lambda: now).execute(),
            lambda: UpdateSyncSettings(uow).execute(
                UpdateSyncSettingsCommand(SyncSettings(nightly_hour=4))
            ),
        ]
        futures = [pool.submit(execute, operation) for operation in operations]
        for future in futures:
            future.result(timeout=20)
    with uow() as unit:
        assert unit.repository.settings().nightly_hour == 4
        assert unit.repository.state().requested
        assert unit.repository.heartbeat() == now
    with Session(engine) as session:
        assert session.get(TeamMatch, match_id).details_imported_at is not None
        assert session.get(SyncAutomation, 1) is not None
    lock = SqlCompetitionWorkerLock(engine)
    with lock.acquire() as first, lock.acquire() as second:
        assert first and not second
    with lock.acquire() as next_owner:
        assert next_owner


def test_outbox_upgrade_preserves_existing_data(postgres_database):
    engine, config = postgres_database
    command.upgrade(config, "d490e19c6832")
    with Session(engine) as session:
        session.add(Season(start_year=2026, end_year=2027, half=SeasonHalf.VR))
        session.commit()

    command.upgrade(config, "head")
    command.check(config)
    with Session(engine) as session:
        assert session.exec(select(Season)).one().start_year == 2026
        assert session.exec(select(OutboxMessage)).all() == []

    # This downgrade removes only the new, empty outbox in the disposable DB.
    command.downgrade(config, "d490e19c6832")
    assert "outbox_message" not in inspect(engine).get_table_names()
    command.upgrade(config, "head")
    command.check(config)
    with Session(engine) as session:
        assert session.exec(select(Season)).one().start_year == 2026


@pytest.mark.parametrize("force", [False, True])
def test_parallel_imports_emit_only_one_event(postgres_database, force):
    engine, config = postgres_database
    command.upgrade(config, "head")
    with Session(engine) as session:
        season = Season(start_year=2026, end_year=2027, half=SeasonHalf.VR)
        session.add(season)
        session.flush()
        group = LeagueGroup(season_id=season.id, name="Liga", mytt_group_id=1)
        session.add(group)
        session.flush()
        team = Team(
            season_id=season.id, league_group_id=group.id, mytt_team_id=1, name="TTC"
        )
        session.add(team)
        session.flush()
        match = TeamMatch(
            team_id=team.id,
            mytt_meeting_id=123,
            opponent_name="Gast",
            is_home=True,
            scheduled_at=datetime(2026, 9, 15, tzinfo=timezone.utc),
            status="completed",
            is_completed=True,
        )
        session.add(match)
        session.commit()
        match_id = match.id

    barrier = Barrier(2)

    class Source:
        async def meeting(self, external_id):
            # Both readers see an unimported match before either writer begins.
            barrier.wait(timeout=10)
            return MeetingDetails(completed=True, score_home=7, score_away=3)

    def run_import():
        sync = build_competition(
            session_factory=lambda: Session(engine), source=Source()
        ).meeting
        return asyncio.run(
            sync.execute(
                SyncMeetingCommand(
                    match_id, force=force, import_origin=ImportOrigin.CURRENT
                )
            )
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run_import) for _ in range(2)]
        results = [future.result(timeout=20) for future in futures]
    assert sum(results) == (2 if force else 1)
    with Session(engine) as session:
        assert (
            session.exec(select(OutboxMessage)).one().payload["team_match_id"]
            == match_id
        )
        assert session.get(TeamMatch, match_id).details_imported_at is not None
