import asyncio
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock

import app.model_registry  # noqa: F401
import pytest
from app.adapters.outbound.persistence.competition.automation import (
    SqlAutomationUnitOfWork,
    SyncAutomation,
)
from app.adapters.outbound.persistence.competition.matches import TeamMatch
from app.core.competition.application.events import ImportOrigin
from app.core.competition.application.sync.automation.commands import (
    RecordWorkerHeartbeat,
    RequestSync,
    RunScheduledSync,
    UpdateSyncSettings,
)
from app.core.competition.application.sync.automation.dto import (
    UpdateSyncSettingsCommand,
)
from app.core.competition.application.sync.automation.queries import GetSyncStatus
from app.core.competition.domain.sync_automation import SyncRun, SyncSettings
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

NOW = datetime(2026, 9, 18, 21, tzinfo=timezone.utc)  # Friday 23:00 Berlin


@pytest.fixture
def automation():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(SyncAutomation(id=1, settings=asdict(SyncSettings()), state={}))
        session.commit()
    uow = lambda: SqlAutomationUnitOfWork(lambda: Session(engine))
    now = [NOW]
    clock = lambda: now[0]
    competition = Mock()
    for name in ("schedule", "meeting", "standings", "registrations"):
        getattr(competition, name).execute = AsyncMock(return_value=True)
    reader = Mock()
    reader.season_id.return_value = 1
    reader.group_ids.return_value = [10]
    scheduler = RunScheduledSync(uow, competition, reader, clock, sleep=AsyncMock())
    status = GetSyncStatus(uow, clock)
    yield engine, uow, now, competition, scheduler, status
    engine.dispose()


def seed_match(engine, match_id=1, scheduled=NOW - timedelta(hours=3), imported=None):
    with Session(engine) as session:
        session.add(
            TeamMatch(
                id=match_id,
                team_id=1,
                mytt_meeting_id=match_id,
                opponent_name="Gast",
                is_home=True,
                scheduled_at=scheduled,
                status="scheduled",
                details_imported_at=imported,
            )
        )
        session.commit()


def finish_nightly(automation):
    asyncio.run(automation[4].execute())


def test_nightly_catches_up_once_and_next_day_runs(automation):
    _, _, now, competition, scheduler, status = automation
    finish_nightly(automation)
    asyncio.run(scheduler.execute())
    competition.schedule.execute.assert_awaited_once()
    competition.standings.execute.assert_awaited_once()
    competition.registrations.execute.assert_awaited_once()
    assert status.execute().state.nightly_run.status == "succeeded"
    assert status.execute().next_nightly_at == datetime(
        2026, 9, 19, 1, tzinfo=timezone.utc
    )
    now[0] = datetime(2026, 9, 19, 1, tzinfo=timezone.utc)
    asyncio.run(scheduler.execute())
    assert competition.schedule.execute.await_count == 2


def test_three_hours_retry_reschedule_and_expiry(automation):
    engine, _, now, competition, scheduler, status = automation
    finish_nightly(automation)
    seed_match(engine, scheduled=NOW - timedelta(hours=3) + timedelta(minutes=1))
    competition.meeting.execute.return_value = False
    asyncio.run(scheduler.execute())
    competition.meeting.execute.assert_not_awaited()
    now[0] += timedelta(minutes=1)
    asyncio.run(scheduler.execute())
    assert status.execute().state.last_run.status == "waiting"
    assert (
        competition.meeting.execute.await_args.args[0].import_origin
        == ImportOrigin.CURRENT
    )
    now[0] += timedelta(minutes=29)
    asyncio.run(scheduler.execute())
    assert competition.meeting.execute.await_count == 1
    now[0] += timedelta(minutes=1)
    asyncio.run(scheduler.execute())
    assert competition.meeting.execute.await_count == 2
    with Session(engine) as session:
        match = session.get(TeamMatch, 1)
        match.scheduled_at = now[0] - timedelta(hours=3)
        session.commit()
    asyncio.run(scheduler.execute())
    assert (
        competition.meeting.execute.await_count == 3
    )  # rescheduled: previous attempt no longer applies
    now[0] += timedelta(hours=24, seconds=1)
    asyncio.run(scheduler.execute())  # nightly catch-up
    asyncio.run(scheduler.execute())
    assert competition.meeting.execute.await_count == 3
    assert status.execute().next_match_at is None


def test_imported_historical_and_future_matches_are_not_fetched(automation):
    engine, _, _, competition, scheduler, _ = automation
    finish_nightly(automation)
    seed_match(engine, 1, imported=NOW)
    seed_match(engine, 2, scheduled=NOW - timedelta(days=30))
    seed_match(engine, 3, scheduled=NOW + timedelta(days=1))
    asyncio.run(scheduler.execute())
    competition.meeting.execute.assert_not_awaited()


def test_settings_apply_live_and_manual_requests_survive_pause(automation):
    _, uow, _, competition, scheduler, status = automation
    UpdateSyncSettings(uow).execute(
        UpdateSyncSettingsCommand(
            SyncSettings(
                enabled=False, include_tables=False, include_registrations=False
            )
        )
    )
    asyncio.run(scheduler.execute())
    competition.schedule.execute.assert_not_awaited()
    RequestSync(uow).execute()
    RequestSync(uow).execute()
    asyncio.run(scheduler.execute())
    asyncio.run(scheduler.execute())
    competition.schedule.execute.assert_awaited_once()
    competition.standings.execute.assert_not_awaited()
    assert status.execute().state.last_run.kind == "manual"
    assert status.execute().next_nightly_at is None


def test_status_is_visible_during_io_and_concurrent_request_not_lost(automation):
    _, uow, now, competition, scheduler, status = automation
    RecordWorkerHeartbeat(uow, lambda: now[0]).execute()

    async def schedule(_):
        current = status.execute()
        assert current.running and current.state.last_run.finished_at is None
        RequestSync(uow).execute()
        return True

    competition.schedule.execute.side_effect = schedule
    asyncio.run(scheduler.execute())
    assert status.execute().state.requested
    now[0] += timedelta(seconds=91)
    assert not status.execute().worker_online


def test_failure_is_retained_and_later_matches_still_run(automation):
    engine, _, _, competition, scheduler, status = automation
    competition.schedule.execute.side_effect = TimeoutError("secret credentials")
    asyncio.run(scheduler.execute())
    assert status.execute().state.last_error == "TimeoutError"
    assert status.execute().state.last_nightly_success_at is None
    seed_match(engine)
    asyncio.run(scheduler.execute())
    assert status.execute().state.last_run.kind == "match"
    assert status.execute().state.nightly_run.status == "failed"
    assert status.execute().state.last_error == "TimeoutError"


def test_restart_recovers_abandoned_run(automation):
    _, uow, _, competition, scheduler, status = automation
    with uow() as unit:
        state = unit.repository.state()
        state.last_run = SyncRun("nightly", NOW - timedelta(hours=1))
        unit.repository.save_state(state)
        unit.commit()
    assert status.execute().stale_run
    asyncio.run(scheduler.execute())
    competition.schedule.execute.assert_awaited_once()
    assert "unterbrochen" in status.execute().state.last_error
    assert not status.execute().stale_run


def test_final_unavailable_result_is_visible_as_error(automation):
    engine, _, _, competition, scheduler, status = automation
    finish_nightly(automation)
    seed_match(engine, scheduled=NOW - timedelta(hours=27))
    competition.meeting.execute.return_value = False
    asyncio.run(scheduler.execute())
    assert status.execute().state.last_run.status == "failed"
    assert "Abruffensters" in status.execute().state.last_error
    assert status.execute().next_match_at is None


@pytest.mark.parametrize(
    "now,expected",
    [
        (
            datetime(2026, 3, 29, 1, 29, tzinfo=timezone.utc),
            datetime(2026, 3, 28, 1, 30, tzinfo=timezone.utc),
        ),
        (
            datetime(2026, 3, 29, 1, 30, tzinfo=timezone.utc),
            datetime(2026, 3, 29, 1, 30, tzinfo=timezone.utc),
        ),
        (
            datetime(2026, 10, 25, 1, 30, tzinfo=timezone.utc),
            datetime(2026, 10, 25, 0, 30, tzinfo=timezone.utc),
        ),
    ],
)
def test_dst_nightly_slot(now, expected):
    assert SyncSettings(nightly_hour=2, nightly_minute=30).nightly_slot(now) == expected


@pytest.mark.parametrize(
    "values", [{"result_retry_minutes": 0}, {"nightly_hour": 24}, {"enabled": "yes"}]
)
def test_invalid_settings(values):
    with pytest.raises(ValueError):
        SyncSettings(**values)


def test_partial_general_run_preserves_last_success_and_continues(automation):
    _, uow, now, competition, scheduler, status = automation
    finish_nightly(automation)
    previous_success = status.execute().state.last_nightly_success_at
    now[0] += timedelta(minutes=1)
    competition.standings.execute.side_effect = TimeoutError("private response")
    RequestSync(uow).execute()
    asyncio.run(scheduler.execute())
    result = status.execute()
    assert result.state.nightly_run.status == "partial"
    assert result.state.nightly_run.errors == ["table group=10: TimeoutError"]
    assert result.state.last_nightly_success_at == previous_success
    assert competition.registrations.execute.await_count == 2


def test_empty_schedule_is_reported_without_stale_group_import(automation):
    _, _, _, competition, scheduler, status = automation
    competition.schedule.execute.return_value = False
    asyncio.run(scheduler.execute())
    assert status.execute().state.last_error == "Keine Spielplandaten erhalten."
    competition.standings.execute.assert_not_awaited()
