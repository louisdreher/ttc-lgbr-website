import ast
import asyncio
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import app.model_registry  # noqa: F401
import httpx
import pytest
from app.adapters.outbound.competition.events import CompetitionMatchEvents
from app.adapters.outbound.mytischtennis.source import MyTischtennisSource
from app.adapters.outbound.persistence.competition.leagues import (
    LeagueGroup,
    LeagueTableEntry,
)
from app.adapters.outbound.persistence.competition.matches import (
    Match,
    MatchLineup,
    MatchParticipant,
    SetResult,
    TeamMatch,
    TeamMatchNotice,
)
from app.adapters.outbound.persistence.competition.reader import SqlCompetitionReader
from app.adapters.outbound.persistence.competition.repository import (
    SqlCompetitionRepository,
)
from app.adapters.outbound.persistence.competition.teams import TeamMembership
from app.adapters.outbound.persistence.events.models import Event
from app.bootstrap.competition_sync import build_competition
from app.core.competition.application.events import ImportOrigin
from app.core.competition.application.sync.batches import ImportBatch
from app.core.competition.application.sync.commands import SyncExternalMeeting
from app.core.competition.application.sync.dto import (
    SyncCurrentCommand,
    SyncExternalMeetingCommand,
    SyncGroupCommand,
    SyncHistoryCommand,
    SyncMeetingCommand,
    SyncScheduleCommand,
)
from app.core.competition.application.sync.errors import SourceError
from app.core.competition.domain.seasons import SeasonHalf, SeasonKey
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

SEASON = SeasonKey(2026, 2027, SeasonHalf.VR)


def schedule_row():
    return {
        "meeting_id": 10,
        "round_type": 0,
        "team_home_club_id": "1",
        "team_away_club_id": "2",
        "team_home_id": 20,
        "team_away_id": 30,
        "team_home": "TTC I",
        "team_away": "Gast",
        "league_id": 40,
        "league_name": " Liga 1",
        "date": "2026-09-01T18:00:00+00:00",
        "is_meeting_complete": True,
        "matches_won": 7,
        "matches_lost": 3,
        "state": "completed",
        "is_letter_h": True,
        "letter_h_info": "Hinweis",
    }


def meeting_response():
    return {
        "data": {
            "is_completed": True,
            "matches_home": 7,
            "matches_guest": 3,
            "match": [
                {
                    "game_type": "single",
                    "match_uuid": "game-1",
                    "matches_home": 1,
                    "mm_player11": {
                        "person_id": "NU1",
                        "player_id": "100",
                        "firstname": "Anna",
                        "lastname": "A",
                        "player_rank": 1,
                    },
                    "mm_player21": {
                        "person_id": "NU2",
                        "firstname": "Bea",
                        "lastname": "B",
                    },
                    "set1_home": 11,
                    "set1_guest": 8,
                    "set2_home": 0,
                    "set2_guest": 0,
                },
                {
                    "game_type": "double",
                    "matches_home": 0,
                    "matches_guest": 0,
                    "mm_player11": {
                        "person_id": "NU1",
                        "player_id": "100",
                        "firstname": "Anna",
                        "lastname": "A",
                        "player_rank": 2,
                    },
                },
            ],
        }
    }


def table_row():
    return dict(
        team_id=20,
        club_id="1",
        team_name="TTC I",
        table_rank=1,
        **{
            key: 1
            for key in (
                "meetings_count",
                "meetings_won",
                "meetings_tie",
                "meetings_lost",
                "points_won",
                "points_lost",
                "matches_won",
                "matches_lost",
                "sets_won",
                "sets_lost",
                "games_won",
                "games_lost",
            )
        },
    )


def registration_response():
    return {
        "data": {
            "teampools": [
                {
                    "clubnr": "1",
                    "team_name": "TTC I",
                    "teampool": [
                        {
                            "team_number": 1,
                            "player_id": "NU1",
                            "player_firstname": "Anna",
                            "player_lastname": "A",
                            "player_rank": "1.1",
                        }
                    ],
                }
            ]
        }
    }


@pytest.fixture
def imports():
    engine = create_engine("sqlite://", poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    SQLModel.metadata.create_all(engine)
    client = AsyncMock()
    client.get_club_schedule_data.return_value = {"data": {"day": [schedule_row()]}}
    client.get_meeting.return_value = meeting_response()
    client.get_team_registrations.return_value = registration_response()
    client.get_team_player_balances.return_value = {
        "urlid": 40,
        "tableData": {"table": [table_row()]},
    }
    sleep = AsyncMock()
    usecases = build_competition(
        session_factory=lambda: Session(engine),
        source=MyTischtennisSource(client, "1"),
        today=lambda: date(2026, 9, 8),
        clock=lambda: datetime(2026, 9, 8, tzinfo=timezone.utc),
        sleep=sleep,
    )
    yield engine, client, usecases, sleep
    engine.dispose()


def seed(imports):
    engine, _, usecases, _ = imports
    asyncio.run(usecases.schedule.execute(SyncScheduleCommand(SEASON)))
    with Session(engine) as session:
        return session.exec(select(TeamMatch.id)).one(), session.exec(
            select(LeagueGroup.id)
        ).one()










def test_schedule_idempotency_rescheduling_notices_and_events(imports):
    engine, client, usecases, _ = imports
    match_id, _ = seed(imports)
    asyncio.run(usecases.schedule.execute(SyncScheduleCommand(SEASON)))
    with Session(engine) as session:
        assert len(session.exec(select(TeamMatch)).all()) == 1
        assert len(session.exec(select(Event)).all()) == 1
        assert session.get(TeamMatch, match_id).original_scheduled_at is None
    row = schedule_row()
    row.update(date="2026-09-03T18:00:00+00:00", is_letter_h=False)
    client.get_club_schedule_data.return_value = {"data": {"day": [row, row]}}
    asyncio.run(usecases.schedule.execute(SyncScheduleCommand(SEASON)))
    with Session(engine) as session:
        match = session.get(TeamMatch, match_id)
        assert match.original_scheduled_at.day == 1
        assert match.scheduled_at.day == 3
        assert session.exec(select(TeamMatchNotice)).all() == []
        assert len(session.exec(select(Event)).all()) == 1


def test_event_failure_rolls_back_entire_schedule(imports, monkeypatch):
    engine, _, usecases, _ = imports

    def fail(*args):
        raise RuntimeError("event failed")

    monkeypatch.setattr(CompetitionMatchEvents, "synchronize", fail)
    with pytest.raises(RuntimeError, match="event failed"):
        asyncio.run(usecases.schedule.execute(SyncScheduleCommand(SEASON)))
    with Session(engine) as session:
        assert session.exec(select(TeamMatch)).all() == []
        assert session.exec(select(LeagueGroup)).all() == []


def test_meeting_lineups_results_and_force_are_idempotent(imports):
    engine, client, usecases, _ = imports
    match_id, _ = seed(imports)
    assert asyncio.run(usecases.meeting.execute(SyncMeetingCommand(match_id)))
    assert not asyncio.run(usecases.meeting.execute(SyncMeetingCommand(match_id)))
    assert asyncio.run(
        usecases.meeting.execute(SyncMeetingCommand(match_id, force=True))
    )
    assert client.get_meeting.await_count == 2
    with Session(engine) as session:
        assert len(session.exec(select(Match)).all()) == 1
        lineup = session.exec(select(MatchLineup)).one()
        assert (lineup.position, lineup.doubles_pair) == (1, 2)
        assert session.exec(select(MatchParticipant)).one().opponent_name == "Bea B"
        result = session.exec(select(SetResult)).one()
        assert (result.points_ttc, result.points_opponent) == (11, 8)


def test_failed_force_import_preserves_previous_details(imports, monkeypatch):
    engine, _, usecases, _ = imports
    match_id, _ = seed(imports)
    asyncio.run(usecases.meeting.execute(SyncMeetingCommand(match_id)))
    original = SqlCompetitionRepository.save_team_match

    def fail(self, *args):
        original(self, *args)
        raise RuntimeError("after flush")

    monkeypatch.setattr(SqlCompetitionRepository, "save_team_match", fail)
    with pytest.raises(RuntimeError, match="after flush"):
        asyncio.run(usecases.meeting.execute(SyncMeetingCommand(match_id, True)))
    with Session(engine) as session:
        assert len(session.exec(select(Match)).all()) == 1
        assert len(session.exec(select(SetResult)).all()) == 1
        assert session.get(TeamMatch, match_id).details_imported_at is not None


def test_registration_replacement_and_invalid_snapshot_preserve_memberships(imports):
    engine, client, usecases, _ = imports
    _, group_id = seed(imports)
    command = SyncGroupCommand(group_id)
    assert asyncio.run(usecases.registrations.execute(command))
    assert asyncio.run(usecases.registrations.execute(command))
    with Session(engine) as session:
        assert len(session.exec(select(TeamMembership)).all()) == 1
    response = registration_response()
    del response["data"]["teampools"][0]["teampool"][0]["player_id"]
    client.get_team_registrations.return_value = response
    with pytest.raises(SourceError):
        asyncio.run(usecases.registrations.execute(command))
    with Session(engine) as session:
        assert session.exec(select(TeamMembership)).one().rank == "1.1"
    response["data"]["teampools"][0]["teampool"] = []
    assert asyncio.run(usecases.registrations.execute(command))
    with Session(engine) as session:
        assert session.exec(select(TeamMembership)).all() == []


@pytest.mark.parametrize(
    "response",
    [
        {"urlid": 40, "tableData": {"table": []}},
        {"urlid": 999, "tableData": {"table": [table_row()]}},
        {"urlid": 40, "tableData": {"table": [{"team_id": 20}]}},
    ],
)
def test_empty_or_invalid_table_preserves_existing_rows(imports, response):
    engine, client, usecases, _ = imports
    _, group_id = seed(imports)
    command = SyncGroupCommand(group_id)
    assert asyncio.run(usecases.standings.execute(command))
    client.get_team_player_balances.return_value = response
    if response["tableData"]["table"]:
        with pytest.raises(SourceError):
            asyncio.run(usecases.standings.execute(command))
    else:
        assert not asyncio.run(usecases.standings.execute(command))
    with Session(engine) as session:
        assert session.exec(select(LeagueTableEntry)).one().team_name == "TTC I"


@pytest.mark.parametrize(
    "workflow,command,origin",
    [
        ("current", SyncCurrentCommand("meetings"), ImportOrigin.CURRENT),
        ("history", SyncHistoryCommand("meetings"), ImportOrigin.HISTORY),
    ],
)
def test_meeting_batches_pass_their_import_origin(
    imports, monkeypatch, workflow, command, origin
):
    _, _, usecases, _ = imports
    seed(imports)
    execute = AsyncMock(return_value=True)
    monkeypatch.setattr(usecases.meeting, "execute", execute)

    summary = asyncio.run(getattr(usecases, workflow).execute(command))

    assert summary.imported == 1
    execute.assert_awaited_once()
    assert execute.await_args.args[0].import_origin is origin


@pytest.mark.parametrize("origin", list(ImportOrigin))
def test_external_meeting_preserves_origin_and_force(origin):
    reader = Mock()
    reader.match_id.return_value = 123
    meeting = Mock()
    meeting.execute = AsyncMock(return_value=True)

    assert asyncio.run(
        SyncExternalMeeting(reader, meeting).execute(
            SyncExternalMeetingCommand(456, force=True, import_origin=origin)
        )
    )

    reader.match_id.assert_called_once_with(456)
    meeting.execute.assert_awaited_once_with(
        SyncMeetingCommand(123, force=True, import_origin=origin)
    )


def test_direct_meeting_import_defaults_to_manual_origin():
    assert SyncMeetingCommand(123).import_origin is ImportOrigin.MANUAL
    assert SyncExternalMeetingCommand(456).import_origin is ImportOrigin.MANUAL


def test_current_and_historical_imports_share_usecases(imports):
    engine, client, usecases, _ = imports
    result = asyncio.run(usecases.current.execute(SyncCurrentCommand("registrations")))
    assert result.imported == 1 and not result.failed
    result = asyncio.run(usecases.history.execute(SyncHistoryCommand("meetings")))
    assert result.imported == 1
    result = asyncio.run(usecases.history.execute(SyncHistoryCommand("tables")))
    assert result.imported == 1
    result = asyncio.run(usecases.history.execute(SyncHistoryCommand("tables")))
    assert result.skipped == 1
    assert client.get_team_player_balances.await_count == 1
    result = asyncio.run(
        usecases.history.execute(SyncHistoryCommand("registrations", 2026, 2026))
    )
    assert result.imported == 1
    reader = SqlCompetitionReader(lambda: Session(engine))
    assert reader.season_id(SEASON) is not None


@pytest.mark.parametrize(
    "status,retryable", [(403, True), (429, True), (503, True), (404, False)]
)
def test_transport_errors_become_core_errors(status, retryable):
    client = AsyncMock()
    request = httpx.Request("GET", "https://example.invalid")
    response = httpx.Response(status, request=request)
    client.get_meeting.side_effect = httpx.HTTPStatusError(
        "failure", request=request, response=response
    )
    with pytest.raises(SourceError) as error:
        asyncio.run(MyTischtennisSource(client, "1").meeting(1))
    assert error.value.retryable is retryable


def test_batch_retries_without_real_sleep_and_reports_failures():
    sleep, operation = AsyncMock(), AsyncMock()
    operation.side_effect = [
        SourceError("temporary", retryable=True),
        True,
        ValueError("invalid"),
    ]
    summary = asyncio.run(ImportBatch(sleep).run([1, 2], operation, attempts=3))
    assert (summary.imported, summary.failed) == (1, [2])
    assert [call.args[0] for call in sleep.await_args_list] == [3, 1]


@pytest.mark.parametrize(
    "today,expected",
    [
        (date(2026, 6, 30), SeasonKey(2025, 2026, SeasonHalf.RR)),
        (date(2026, 7, 1), SEASON),
    ],
)
def test_current_half_season(today, expected):
    assert SeasonKey.current(today) == expected


def test_competition_import_core_has_no_infrastructure_dependencies():
    root = Path(__file__).resolve().parents[1] / "app" / "core" / "competition"
    for directory in ("application", "domain"):
        for path in (root / directory).rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                imports = (
                    [alias.name for alias in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                    if isinstance(node, ast.ImportFrom)
                    else []
                )
                for name in imports:
                    assert not name.startswith(
                        (
                            "sqlmodel",
                            "sqlalchemy",
                            "fastapi",
                            "httpx",
                            "pydantic",
                            "app.adapters",
                            "app.bootstrap",
                            "app.integrations",
                        )
                    ), (path, name)
                    if name.startswith("app.core.competition"):
                        assert name.startswith(
                            (
                                "app.core.competition.application",
                                "app.core.competition.domain",
                            )
                        ), (path, name)


@pytest.mark.parametrize(
    "kind,method",
    [("registrations", "save_team"), ("standings", "save_group")],
)
def test_replacement_failure_rolls_back_existing_data(
    imports, monkeypatch, kind, method
):
    engine, client, usecases, _ = imports
    _, group_id = seed(imports)
    operation = getattr(usecases, kind)
    asyncio.run(operation.execute(SyncGroupCommand(group_id)))
    original = getattr(SqlCompetitionRepository, method)

    def fail(self, *args):
        original(self, *args)
        raise RuntimeError("after replacement")

    monkeypatch.setattr(SqlCompetitionRepository, method, fail)
    if kind == "registrations":
        client.get_team_registrations.return_value["data"]["teampools"][0][
            "teampool"
        ] = []
    else:
        client.get_team_player_balances.return_value["tableData"]["table"][0][
            "team_name"
        ] = "Changed"
    with pytest.raises(RuntimeError, match="after replacement"):
        asyncio.run(operation.execute(SyncGroupCommand(group_id)))
    with Session(engine) as session:
        if kind == "registrations":
            assert session.exec(select(TeamMembership)).one().rank == "1.1"
        else:
            assert session.exec(select(LeagueTableEntry)).one().team_name == "TTC I"


def test_unsupported_schedule_keeps_season_without_importing_cup(imports):
    engine, client, usecases, _ = imports
    client.get_club_schedule_data.return_value["data"]["day"][0]["round_type"] = 4
    assert asyncio.run(usecases.schedule.execute(SyncScheduleCommand(SEASON)))
    assert SqlCompetitionReader(lambda: Session(engine)).season_id(SEASON) is not None
    with Session(engine) as session:
        assert session.exec(select(TeamMatch)).all() == []


def test_member_identity_conflict_rolls_back_meeting(imports):
    from app.adapters.outbound.persistence.members.models import Member, Player

    engine, _client, usecases, _ = imports
    match_id, _ = seed(imports)
    with Session(engine) as session:
        one, two = (
            Member(first_name="One", last_name="A"),
            Member(first_name="Two", last_name="B"),
        )
        session.add_all([one, two])
        session.flush()
        session.add_all(
            [
                Player(member_id=one.id, nuid="NU1"),
                Player(member_id=two.id, mytt_person_id="100"),
            ]
        )
        session.commit()
    with pytest.raises(ValueError, match="Spieler-ID-Konflikt"):
        asyncio.run(usecases.meeting.execute(SyncMeetingCommand(match_id)))
    with Session(engine) as session:
        assert session.get(TeamMatch, match_id).details_imported_at is None
        assert session.exec(select(Match)).all() == []


def test_absent_opponent_and_away_scores(imports):
    engine, client, usecases, _ = imports
    match_id, _ = seed(imports)
    response = meeting_response()
    game = response["data"]["match"][0]
    game["mm_player11"], game["mm_player21"] = game["mm_player21"], game["mm_player11"]
    game["mm_player11"] = {"person_id": "NU74837"}
    response["data"]["match"] = [game]
    client.get_meeting.return_value = response
    with Session(engine) as session:
        match = session.get(TeamMatch, match_id)
        match.is_home = False
        session.commit()
    assert asyncio.run(usecases.meeting.execute(SyncMeetingCommand(match_id)))
    with Session(engine) as session:
        match = session.get(TeamMatch, match_id)
        assert (match.score_ttc, match.score_opponent) == (3, 7)
        assert (
            session.exec(select(MatchParticipant)).one().opponent_name
            == "Nicht anwesend"
        )
        result = session.exec(select(SetResult)).one()
        assert (result.points_ttc, result.points_opponent) == (8, 11)


@pytest.mark.parametrize(
    "module",
    [
        "run_current_sync",
        "history.import_schedule",
        "history.import_meetings",
        "history.import_registrations",
        "history.import_league_tables",
        "diagnostics.sync_single_meeting",
        "diagnostics.probe_client",
        "diagnostics.probe_registrations",
    ],
)
def test_cli_help_without_external_requests(module):
    backend = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-m", f"scripts.mytt.{module}", "--help"],
        cwd=backend,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()


def test_schedule_usecase_accepts_memory_ports():
    from types import SimpleNamespace
    from unittest.mock import Mock

    from app.core.competition.application.sync.commands import SyncSchedule
    from app.core.competition.application.sync.imports import ScheduleSnapshot
    from app.core.competition.application.sync.ports import CompetitionRepository
    from app.core.competition.domain.matches import TeamMatch as DomainTeamMatch

    calls = []
    repository = Mock(spec=CompetitionRepository)
    for method in ("find_season", "find_group", "find_team", "find_team_match"):
        getattr(repository, method).return_value = None
    saved = []

    def save(entity):
        entity.id = 1
        saved.append(entity)

    for method in ("save_season", "save_group", "save_team", "save_team_match"):
        getattr(repository, method).side_effect = save

    class MemoryUnitOfWork:
        events = SimpleNamespace(synchronize=lambda match_id: calls.append(match_id))

        def __init__(self):
            self.repository = repository

        def __enter__(self):
            calls.append("begin")
            return self

        def commit(self):
            calls.append("commit")

        def __exit__(self, *args):
            calls.append("end")

    source = AsyncMock()

    async def fetch(key):
        assert calls == []  # No write transaction across the external await.
        assert key == SEASON
        data = MyTischtennisSource(None, "1")._scheduled_match(schedule_row())
        return ScheduleSnapshot((data,), 1)

    source.schedule.side_effect = fetch
    assert asyncio.run(
        SyncSchedule(source, MemoryUnitOfWork()).execute(SyncScheduleCommand(SEASON))
    )
    assert calls == ["begin", 1, "commit", "end"]
    assert isinstance(saved[-1], DomainTeamMatch)
    assert saved[-1].opponent_name == "Gast"


def test_missing_registration_pool_preserves_memberships(imports):
    engine, client, usecases, _ = imports
    _, group_id = seed(imports)
    asyncio.run(usecases.registrations.execute(SyncGroupCommand(group_id)))
    del client.get_team_registrations.return_value["data"]["teampools"][0]["teampool"]
    with pytest.raises(SourceError):
        asyncio.run(usecases.registrations.execute(SyncGroupCommand(group_id)))
    with Session(engine) as session:
        assert len(session.exec(select(TeamMembership)).all()) == 1


def test_registration_report_uses_reader_projection(imports):
    from app.adapters.outbound.persistence.competition.diagnostics import (
        SqlRegistrationReportReader,
    )
    from app.core.competition.application.sync.queries import GetRegistrationReport

    engine, _, usecases, _ = imports
    _, group_id = seed(imports)
    report = GetRegistrationReport(SqlRegistrationReportReader(engine))
    summary, details = report.execute()
    assert summary[0]["teams"] == 1 and len(details) == 1
    asyncio.run(usecases.registrations.execute(SyncGroupCommand(group_id)))
    summary, details = report.execute()
    assert summary[0]["memberships"] == 1 and details == []


def test_http_client_url_mapping_and_rate_limit_without_network(monkeypatch):
    from app.adapters.outbound.mytischtennis.client import MyTischtennisClient

    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(429, json={"error": "rate limit"})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: real_client(**kwargs, transport=httpx.MockTransport(respond)),
    )
    client = MyTischtennisClient(
        base_url="https://example.invalid",
        organization="test",
        club_number="1",
        club_slug="TTC",
    )
    with pytest.raises(SourceError) as error:
        asyncio.run(MyTischtennisSource(client, "1").schedule(SEASON))
    assert error.value.retryable
    assert requests[0].url.path == "/click-tt/test/26--27/verein/1/TTC/spielplan"
    assert requests[0].url.params["date_start"] == "2026-07-01"
    assert requests[0].url.params["date_end"] == "2026-12-31"


def test_cli_batch_failure_has_nonzero_exit_code(monkeypatch):
    from types import SimpleNamespace

    from app.adapters.inbound.cli import competition
    from app.core.competition.application.sync.dto import ImportSummary

    operation = SimpleNamespace(
        execute=AsyncMock(return_value=ImportSummary(failed=[1]))
    )
    monkeypatch.setattr(competition, "configure_logging", lambda **kwargs: None)
    monkeypatch.setattr(
        competition, "build_competition", lambda: SimpleNamespace(current=operation)
    )
    with pytest.raises(SystemExit) as error:
        asyncio.run(competition.main("current", ["meetings"]))
    assert error.value.code == 1


def test_backfill_failure_rolls_back_created_event(imports, monkeypatch):
    from app.bootstrap.competition_sync import build_backfill_match_events
    from app.core.competition.application.sync.dto import BackfillMatchEventsCommand

    engine, _, _, _ = imports
    seed(imports)
    with Session(engine) as session:
        session.delete(session.exec(select(Event)).one())
        session.commit()
    original = CompetitionMatchEvents.synchronize

    def fail_after_save(self, match_id):
        original(self, match_id)
        raise RuntimeError("backfill failed")

    monkeypatch.setattr(CompetitionMatchEvents, "synchronize", fail_after_save)
    with pytest.raises(RuntimeError, match="backfill failed"):
        build_backfill_match_events(lambda: Session(engine)).execute(
            BackfillMatchEventsCommand()
        )
    with Session(engine) as session:
        assert session.exec(select(Event)).all() == []


def test_entity_repository_roundtrip_preserves_imported_graph_and_assignments(imports):
    from datetime import timedelta

    from app.core.competition.domain.matches import TeamMatch as DomainTeamMatch
    from app.core.competition.domain.teams import TeamAssignment

    engine, client, usecases, _ = imports
    match_id, group_id = seed(imports)
    asyncio.run(usecases.meeting.execute(SyncMeetingCommand(match_id)))
    asyncio.run(usecases.registrations.execute(SyncGroupCommand(group_id)))
    asyncio.run(usecases.standings.execute(SyncGroupCommand(group_id)))
    with Session(engine) as session:
        repository = SqlCompetitionRepository(session)
        match = repository.get_team_match(match_id)
        assert isinstance(match, DomainTeamMatch)
        assert len(match.matches) == 1 and len(match.matches[0].sets) == 1
        detail_id = match.matches[0].id
        imported_at = match.details_imported_at
        team = repository.teams_in_group(group_id)[0]
        player_id = team.memberships[0].player_id
        team.assignments = [TeamAssignment(player_id=player_id, position=3)]
        repository.save_team(team)
        group = repository.get_group(group_id)
        repository.save_group(group)
        match.reschedule(match.scheduled_at + timedelta(days=1))
        repository.save_team_match(match)
        session.commit()
    # A schedule refresh must neither rebuild nor discard the imported graph.
    client.get_club_schedule_data.return_value["data"]["day"][0]["date"] = (
        "2026-09-02T18:00:00+00:00"
    )
    asyncio.run(usecases.schedule.execute(SyncScheduleCommand(SEASON)))
    with Session(engine) as session:
        repository = SqlCompetitionRepository(session)
        match = repository.get_team_match(match_id)
        assert match.details_imported_at == imported_at
        assert match.matches[0].id == detail_id
        assert match.matches[0].participants[0].player_id == player_id
        assert match.original_scheduled_at.day == 1
        team = repository.teams_in_group(group_id)[0]
        assert team.assignments[0].position == 3
        assert team.memberships[0].rank == "1.1"
        assert repository.get_group(group_id).table[0].team_name == "TTC I"
