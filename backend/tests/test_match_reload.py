import asyncio
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.adapters.outbound.persistence.articles.models import Article
from app.adapters.outbound.persistence.competition.automation import (
    MatchReloadRequest,
    SqlAutomationUnitOfWork,
    SyncAutomation,
)
from app.adapters.outbound.persistence.competition.matches import TeamMatch
from app.adapters.outbound.persistence.competition.reader import SqlCompetitionReader
from app.adapters.outbound.persistence.competition.sync_overview import (
    SqlSyncMatchOverviewReader,
)
from app.adapters.outbound.persistence.messaging.models import OutboxMessage
from app.bootstrap.messaging import build_process_outbox
from app.core.competition.application.events import ImportOrigin
from app.core.competition.application.sync.automation.commands import (
    RecordWorkerHeartbeat,
    RequestMatchReload,
    RunScheduledSync,
)
from app.core.competition.application.sync.automation.dto import (
    RequestMatchReloadCommand,
)
from app.core.competition.application.sync.automation.errors import (
    MatchReloadConflictError,
    ReloadMatchNotFoundError,
)
from app.core.competition.application.sync.automation.queries import GetSyncMatches
from app.core.competition.domain.sync_automation import SyncRun, SyncSettings
from app.core.messaging.application.dto import ProcessOutboxCommand
from sqlmodel import Session, select
from test_competition_imports import imports  # noqa: F401
from test_report_automation import reports  # noqa: F401

NOW = datetime(2026, 9, 18, 21, tzinfo=timezone.utc)


@pytest.fixture
def reloads(reports):  # noqa: F811
    engine, competition, match_id, _, _ = reports
    with Session(engine) as session:
        session.add(
            SyncAutomation(id=1, settings=asdict(SyncSettings(enabled=False)), state={})
        )
        team_id = session.get(TeamMatch, match_id).team_id
        session.commit()
    uow = lambda: SqlAutomationUnitOfWork(lambda: Session(engine))
    now = [NOW]
    clock = lambda: now[0]
    return SimpleNamespace(
        engine=engine,
        uow=uow,
        now=now,
        clock=clock,
        match_id=match_id,
        team_id=team_id,
        competition=competition,
        request=RequestMatchReload(uow, clock),
        scheduler=RunScheduledSync(
            uow,
            competition,
            SqlCompetitionReader(lambda: Session(engine)),
            clock,
            sleep=AsyncMock(),
        ),
        overview=GetSyncMatches(
            SqlSyncMatchOverviewReader(lambda: Session(engine)), clock
        ),
    )


def enqueue(ctx, match_id=None):
    return ctx.request.execute(RequestMatchReloadCommand(match_id or ctx.match_id))


def job(ctx):
    with ctx.uow() as unit:
        return unit.repository.reload_request(ctx.match_id)


def change_match(ctx, **values):
    with Session(ctx.engine) as session:
        match = session.get(TeamMatch, ctx.match_id)
        for name, value in values.items():
            setattr(match, name, value)
        session.commit()


def test_overview_groups_limits_ties_and_no_writes(reloads):
    ctx = reloads
    with Session(ctx.engine) as session:

        def add(match_id, scheduled_at, completed=False, imported=None, external=True):
            session.add(
                TeamMatch(
                    id=match_id,
                    team_id=ctx.team_id,
                    mytt_meeting_id=1000 + match_id if external else None,
                    opponent_name=f"Gast {match_id}",
                    is_home=False,
                    scheduled_at=scheduled_at,
                    status="completed" if completed else "scheduled",
                    is_completed=completed,
                    details_imported_at=imported,
                )
            )

        for i in range(12):
            add(10 + i, NOW - timedelta(days=30), True, NOW - timedelta(hours=i // 2))
        for i in range(5):
            add(40 + i, NOW + timedelta(hours=1 + i // 2))
        add(50, NOW - timedelta(days=1000), True)
        add(51, NOW - timedelta(days=999), True, external=False)
        add(
            60, NOW + timedelta(hours=10), True
        )  # inconsistent future/completed: only missing
        add(70, NOW - timedelta(days=1))
        add(71, NOW)  # future is strictly > now
        session.commit()
        before = session.get(SyncAutomation, 1).model_dump()
    for _ in range(2):
        overview = ctx.overview.execute()
        assert [m.id for m in overview.imported] == list(range(10, 20))
        assert [m.id for m in overview.missing_details] == [50, 51, ctx.match_id, 60]
        assert [m.id for m in overview.upcoming] == [40, 41, 42]
        missing = overview.missing_details
        assert missing[0].can_reload
        assert missing[0].team_name == "TTC I" and not missing[0].is_home
        assert (
            not missing[1].can_reload and "Spiel-ID" in missing[1].reload_blocked_reason
        )
        assert not overview.imported[0].can_reload
        assert not overview.upcoming[0].can_reload
    with Session(ctx.engine) as session:
        assert session.get(SyncAutomation, 1).model_dump() == before
        assert session.exec(select(MatchReloadRequest)).all() == []
        assert session.exec(select(OutboxMessage)).all() == []


def test_reload_outside_window_while_paused_is_manual_and_creates_no_report(reloads):
    ctx = reloads
    first = enqueue(ctx)
    ctx.now[0] += timedelta(minutes=1)
    assert enqueue(ctx) == first
    assert first.status == "requested" and first.started_at is None
    assert not ctx.overview.execute().missing_details[0].can_reload
    original = ctx.competition.meeting.execute

    async def import_and_inspect(command):
        assert command.import_origin == ImportOrigin.MANUAL and command.force is False
        assert enqueue(ctx).status == "running"
        assert ctx.overview.execute().missing_details[0].reload.status == "running"
        RecordWorkerHeartbeat(ctx.uow, ctx.clock).execute()
        return await original(command)

    ctx.competition.meeting.execute = AsyncMock(side_effect=import_and_inspect)
    assert asyncio.run(ctx.scheduler.execute()).imported == 1
    assert job(ctx).status == "succeeded" and job(ctx).finished_at is not None
    assert asyncio.run(ctx.scheduler.execute()).imported == 0
    ctx.competition.meeting.execute.assert_awaited_once()
    with pytest.raises(MatchReloadConflictError, match="bereits"):
        enqueue(ctx)
    assert ctx.overview.execute().imported[0].reload.status == "succeeded"
    with Session(ctx.engine) as session:
        assert (
            session.exec(select(OutboxMessage)).one().payload["import_origin"]
            == "MANUAL"
        )
        assert len(session.exec(select(MatchReloadRequest)).all()) == 1
    processor = build_process_outbox(
        session_factory=lambda: Session(ctx.engine), clock=ctx.clock
    )
    assert processor.execute(ProcessOutboxCommand()).succeeded == 1
    with Session(ctx.engine) as session:
        assert session.exec(select(Article)).all() == []


@pytest.mark.parametrize(
    "values,reason",
    [
        ({"is_completed": False}, "abgeschlossen"),
        ({"mytt_meeting_id": None}, "Spiel-ID"),
        ({"details_imported_at": NOW}, "bereits"),
    ],
)
def test_invalid_reload_does_not_enqueue(reloads, values, reason):
    change_match(reloads, **values)
    with pytest.raises(MatchReloadConflictError, match=reason):
        enqueue(reloads)
    assert job(reloads) is None


def test_unknown_match(reloads):
    with pytest.raises(ReloadMatchNotFoundError):
        enqueue(reloads, 99999)


def test_failed_manual_request_is_visible_retryable_and_not_automatically_taken_over(
    reloads,
):
    ctx = reloads
    change_match(ctx, scheduled_at=NOW - timedelta(hours=3))
    with ctx.uow() as unit:
        settings = SyncSettings()
        unit.repository.save_settings(settings)
        state = unit.repository.state()
        state.last_nightly_slot = settings.nightly_slot(NOW)
        unit.repository.save_state(state)
        unit.commit()
    original = ctx.competition.meeting.execute
    ctx.competition.meeting.execute = AsyncMock(
        side_effect=RuntimeError("password=secret provider payload")
    )
    enqueue(ctx)
    assert asyncio.run(ctx.scheduler.execute()).failed == [ctx.match_id]
    assert job(ctx).last_error == "RuntimeError"
    overview = ctx.overview.execute().missing_details[0]
    assert overview.can_reload and overview.reload.status == "failed"
    assert overview.reload.last_error == "RuntimeError"
    asyncio.run(ctx.scheduler.execute())
    ctx.competition.meeting.execute.assert_awaited_once()
    ctx.now[0] += timedelta(minutes=1)
    retry = enqueue(ctx)
    assert retry.last_error is None and retry.requested_at == ctx.now[0]
    ctx.competition.meeting.execute = original
    asyncio.run(ctx.scheduler.execute())
    assert job(ctx).status == "succeeded"


def test_unavailable_details_are_failed_not_successful(reloads):
    enqueue(reloads)
    reloads.competition.meeting.execute = AsyncMock(return_value=False)
    assert asyncio.run(reloads.scheduler.execute()).failed
    assert job(reloads).status == "failed"
    assert "keine vollständigen Ergebnisse" in job(reloads).last_error


@pytest.mark.parametrize("commit_results", [False, True])
def test_restart_recovers_interrupted_request_without_reimporting_saved_results(
    reloads, commit_results
):
    ctx = reloads
    original = ctx.competition.meeting.execute

    async def crash(command):
        if commit_results:
            await original(command)
        raise asyncio.CancelledError()

    enqueue(ctx)
    ctx.competition.meeting.execute = AsyncMock(side_effect=crash)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(ctx.scheduler.execute())
    assert job(ctx).status == "running"
    ctx.competition.meeting.execute = AsyncMock(wraps=original)
    restarted = RunScheduledSync(
        ctx.uow,
        ctx.competition,
        SqlCompetitionReader(lambda: Session(ctx.engine)),
        ctx.clock,
    )
    asyncio.run(restarted.execute())
    assert job(ctx).status == "succeeded"
    assert ctx.competition.meeting.execute.await_count == (0 if commit_results else 1)
    with Session(ctx.engine) as session:
        assert len(session.exec(select(OutboxMessage)).all()) == 1


def test_request_has_priority_and_preserves_general_sync_request(reloads):
    ctx = reloads
    with ctx.uow() as unit:
        state = unit.repository.state()
        state.requested = True
        unit.repository.save_state(state)
        unit.commit()
    ctx.competition.schedule.execute = AsyncMock()
    enqueue(ctx)
    asyncio.run(ctx.scheduler.execute())
    ctx.competition.schedule.execute.assert_not_awaited()
    with ctx.uow() as unit:
        assert unit.repository.state().requested
        assert unit.repository.state().nightly_run is None


def test_active_automatic_fetch_blocks_manual_enqueue(reloads):
    ctx = reloads
    with ctx.uow() as unit:
        state = unit.repository.state()
        state.last_run = SyncRun("match", NOW, ctx.match_id)
        unit.repository.save_state(state)
        unit.commit()
    with pytest.raises(MatchReloadConflictError, match="automatischer Abruf"):
        enqueue(ctx)
    assert (
        "automatischer Abruf"
        in ctx.overview.execute().missing_details[0].reload_blocked_reason
    )
    assert job(ctx) is None


@pytest.mark.parametrize("values", [{"is_completed": False}, {"mytt_meeting_id": None}])
def test_worker_revalidates_after_enqueue(reloads, values):
    enqueue(reloads)
    change_match(reloads, **values)
    reloads.competition.meeting.execute = AsyncMock()
    asyncio.run(reloads.scheduler.execute())
    assert job(reloads).status == "failed"
    reloads.competition.meeting.execute.assert_not_awaited()


def test_results_imported_after_enqueue_are_acknowledged_without_fetch(reloads):
    enqueue(reloads)
    change_match(reloads, details_imported_at=NOW)
    reloads.competition.meeting.execute = AsyncMock()
    result = asyncio.run(reloads.scheduler.execute())
    assert result.skipped == 1 and not result.failed
    assert job(reloads).status == "succeeded"
    reloads.competition.meeting.execute.assert_not_awaited()


def test_reload_queue_uses_request_time_then_id(reloads):
    ctx = reloads
    with Session(ctx.engine) as session:
        for match_id in (10, 11):
            session.add(
                TeamMatch(
                    id=match_id,
                    team_id=ctx.team_id,
                    mytt_meeting_id=1000 + match_id,
                    opponent_name="Gast",
                    is_home=True,
                    scheduled_at=NOW - timedelta(days=40),
                    status="completed",
                    is_completed=True,
                )
            )
        session.commit()
    # Reverse enqueue order, same clock: the ID breaks the tie deterministically.
    enqueue(ctx, 11)
    enqueue(ctx, 10)
    ctx.now[0] += timedelta(seconds=1)
    enqueue(ctx)
    ctx.competition.meeting.execute = AsyncMock(return_value=False)
    for _ in range(3):
        asyncio.run(ctx.scheduler.execute())
    assert [
        call.args[0].team_match_id
        for call in ctx.competition.meeting.execute.await_args_list
    ] == [10, 11, ctx.match_id]
