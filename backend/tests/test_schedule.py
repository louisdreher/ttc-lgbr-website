from datetime import date, datetime, timezone

import pytest
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

import app.model_registry  # noqa: F401
from app.adapters.outbound.persistence.competition.leagues import LeagueGroup
from app.adapters.outbound.persistence.competition.matches import TeamMatch
from app.adapters.outbound.persistence.competition.seasons import Season
from app.adapters.outbound.persistence.competition.teams import Team
from app.bootstrap.competition import build_get_schedule
from app.core.competition.application.dto import (
    GetScheduleQuery,
    ScheduledMatchSummary,
)
from app.core.competition.domain.seasons import SeasonHalf


@pytest.fixture
def schedule(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'schedule.db'}")

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    try:
        SQLModel.metadata.create_all(engine)
        with Session(engine) as session:
            session.add_all(
                [
                    Season(
                        id=i, start_year=2025 + i, end_year=2026 + i, half=SeasonHalf.VR
                    )
                    for i in (1, 2)
                ]
            )
            session.flush()
            session.add_all(
                [
                    LeagueGroup(id=i, season_id=i, name="Liga", mytt_group_id=i)
                    for i in (1, 2)
                ]
            )
            session.flush()
            session.add_all(
                [
                    Team(
                        id=i,
                        season_id=1 if i == 3 else i,
                        league_group_id=1 if i == 3 else i,
                        name="Herren I",
                        category="J15" if i == 2 else "H",
                        mytt_team_id=i,
                    )
                    for i in (1, 2, 3)
                ]
            )
            session.flush()
            for match_id, team_id, day in [
                (1, 1, 20),
                (2, 1, 10),
                (3, 1, 10),
                (4, 2, 5),
            ]:
                session.add(
                    TeamMatch(
                        id=match_id,
                        team_id=team_id,
                        opponent_name=f"Gast {match_id}",
                        is_home=match_id != 2,
                        play_mode=None,
                        scheduled_at=datetime(2026, 9, day, 18, tzinfo=timezone.utc),
                        status="finished" if match_id == 2 else "scheduled",
                        is_completed=match_id == 2,
                        score_ttc=7 if match_id == 2 else None,
                        score_opponent=3 if match_id == 2 else None,
                    )
                )
            session.commit()
        yield build_get_schedule(lambda: Session(engine))
    finally:
        engine.dispose()


def test_team_schedule_filters_sorts_and_maps_results(schedule):
    rows = schedule.execute(
        GetScheduleQuery(date(2026, 9, 1), date(2026, 9, 30), team_ids=(1,))
    )
    assert [row.id for row in rows] == [2, 3, 1]
    assert rows[0] == ScheduledMatchSummary(
        id=2,
        team_id=1,
        team_name="Herren I",
        opponent_name="Gast 2",
        is_home=False,
        scheduled_at=datetime(2026, 9, 10, 18, tzinfo=timezone.utc).replace(
            tzinfo=None
        ),
        status="finished",
        is_completed=True,
        score_ttc=7,
        score_opponent=3,
    )
    assert rows[1].score_ttc is None
    assert rows[1].score_opponent is None
    assert rows[1].is_home is True
    assert rows[1].is_completed is False


@pytest.mark.parametrize("team_id", [3, 999])
def test_empty_or_unknown_team_returns_empty_list(schedule, team_id):
    assert (
        schedule.execute(
            GetScheduleQuery(date(2026, 9, 1), date(2026, 9, 30), team_ids=(team_id,))
        )
        == []
    )


@pytest.mark.parametrize("team_ids", [None, ()])
def test_no_teams_means_all_teams(schedule, team_ids):
    rows = schedule.execute(
        GetScheduleQuery(date(2026, 9, 1), date(2026, 9, 30), team_ids)
    )
    assert [row.id for row in rows] == [4, 2, 3, 1]


@pytest.mark.parametrize(
    ("team_ids", "category", "expected"),
    [
        (None, "H", [2, 3, 1]),
        ((1, 2), "J15", [4]),
        ((1,), "J15", []),
        ((1, 2), None, [4, 2, 3, 1]),
    ],
)
def test_category_and_team_filters_combine(schedule, team_ids, category, expected):
    rows = schedule.execute(
        GetScheduleQuery(date(2026, 9, 1), date(2026, 9, 30), team_ids, category)
    )
    assert [row.id for row in rows] == expected


def test_date_range_restricts_selected_teams(schedule):
    rows = schedule.execute(
        GetScheduleQuery(date(2026, 9, 10), date(2026, 9, 10), (1, 2))
    )
    assert [row.id for row in rows] == [2, 3]


def test_invalid_range_does_not_call_reader():
    from unittest.mock import Mock

    from app.core.competition.application.queries import GetSchedule

    reader = Mock()
    with pytest.raises(ValueError):
        GetSchedule(reader).execute(
            GetScheduleQuery(date(2026, 9, 11), date(2026, 9, 10))
        )
    reader.get_schedule.assert_not_called()


@pytest.mark.parametrize(
    ("day", "utc_start", "utc_end"),
    [
        (
            date(2026, 9, 10),
            datetime(2026, 9, 9, 22, tzinfo=timezone.utc),
            datetime(2026, 9, 10, 22, tzinfo=timezone.utc),
        ),
        (
            date(2026, 10, 25),
            datetime(2026, 10, 24, 22, tzinfo=timezone.utc),
            datetime(2026, 10, 25, 23, tzinfo=timezone.utc),
        ),
    ],
)
def test_inclusive_local_day_boundaries(schedule, day, utc_start, utc_end):
    from datetime import timedelta

    # Access the injected test session factory, never the configured database.
    with schedule.reader.session_factory() as session:
        for offset, timestamp in enumerate(
            (
                utc_start - timedelta(microseconds=1),
                utc_start,
                utc_end - timedelta(microseconds=1),
                utc_end,
            )
        ):
            session.add(
                TeamMatch(
                    id=10 + offset,
                    team_id=3,
                    opponent_name="Boundary",
                    is_home=True,
                    play_mode=None,
                    scheduled_at=timestamp,
                    status="scheduled",
                )
            )
        session.commit()
    rows = schedule.execute(GetScheduleQuery(day, day, (3,)))
    assert [row.id for row in rows] == [11, 12]
