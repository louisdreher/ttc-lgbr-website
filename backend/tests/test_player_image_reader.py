import pytest
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

import app.model_registry  # noqa: F401
from app.adapters.outbound.persistence.members.models import PlayerImage
from app.bootstrap.members import build_get_player_images
from app.core.members.public import GetPlayerImagesQuery


@pytest.fixture
def database():
    # FK constraints are separately covered by test_player_images_postgres.py.
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([
            PlayerImage(player_id=1, season_start_year=2009, season_half="vr", media_id=1),
            PlayerImage(player_id=1, season_start_year=2014, season_half="vr", media_id=2),
            PlayerImage(player_id=1, season_start_year=2014, season_half="rr", media_id=3),
            PlayerImage(player_id=1, season_start_year=2020, season_half="vr", media_id=4),
            PlayerImage(player_id=2, season_start_year=2014, season_half="rr", media_id=5),
        ])
        session.commit()
    yield engine
    engine.dispose()


@pytest.mark.parametrize("year,half,expected", [
    (2008, "rr", None), (2009, "vr", 1), (2009, "rr", 1),
    (2013, "rr", 1), (2014, "vr", 2), (2014, "rr", 3),
    (2015, "vr", 3), (2020, "vr", 4), (2026, "rr", 4),
])
def test_historical_image_selection(database, year, half, expected):
    query = GetPlayerImagesQuery(frozenset({1}), year, half)
    assert build_get_player_images(lambda: Session(database)).execute(query) == {1: expected}


def test_batch_read_is_one_select_and_includes_missing_images(database):
    statements = []

    @event.listens_for(database, "before_cursor_execute")
    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    result = build_get_player_images(lambda: Session(database)).execute(
        GetPlayerImagesQuery(frozenset({1, 2, 3, 999}), 2014, "vr")
    )
    assert result == {1: 2, 2: None, 3: None, 999: None}
    assert len(statements) == 1
    assert statements[0].lstrip().upper().startswith("SELECT")


def test_empty_request_does_not_open_session():
    def no_session():
        pytest.fail("Empty lookup must not open a session")

    assert build_get_player_images(no_session).execute(
        GetPlayerImagesQuery(frozenset(), 2026, "vr")
    ) == {}


@pytest.mark.parametrize("ids,year,half", [
    ({1}, 2026, "unknown"), ({1}, 0, "vr"), ({1}, 9999, "rr"),
    ({0}, 2026, "vr"), ({-1}, 2026, "rr"),
])
def test_invalid_query(ids, year, half):
    with pytest.raises(ValueError):
        GetPlayerImagesQuery(frozenset(ids), year, half)


@pytest.mark.parametrize("half,expected", [("vr", 2), ("rr", 3)])
def test_team_lineup_uses_its_historical_half(database, half, expected):
    from unittest.mock import Mock
    from app.core.competition.application.dto import (
        GetTeamLineupQuery, SeasonSummary, TeamLineup, TeamLineupEntry,
    )
    from app.core.competition.application.queries import GetTeamLineup
    from app.core.competition.domain.seasons import SeasonHalf

    reader = Mock()
    original = TeamLineup(8, "Herren III", 42, "H", [
        TeamLineupEntry(1, "Anna", "Test", 1, None),
        TeamLineupEntry(3, "Ben", "Test", 2, None),
    ])
    reader.get_team_lineup.return_value = original
    reader.list_seasons.return_value = [SeasonSummary(42, 2014, 2015, SeasonHalf(half))]
    result = GetTeamLineup(reader, build_get_player_images(lambda: Session(database))).execute(
        GetTeamLineupQuery(8)
    )
    assert [player.media_id for player in result.players] == [expected, None]
    assert original.players[0].media_id is None
