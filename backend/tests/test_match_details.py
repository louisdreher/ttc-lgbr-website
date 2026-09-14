from datetime import datetime, timezone

import pytest
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

import app.model_registry  # noqa: F401
from app.adapters.outbound.persistence.competition.leagues import LeagueGroup
from app.adapters.outbound.persistence.competition.matches import (
    Match,
    MatchLineup,
    MatchParticipant,
    SetResult,
    TeamMatch,
    TeamMatchNotice,
)
from app.adapters.outbound.persistence.competition.seasons import Season
from app.adapters.outbound.persistence.competition.teams import Team, TeamAssignment
from app.adapters.outbound.persistence.members.models import Member, Player
from app.bootstrap.competition import build_get_match_details
from app.core.competition.application.dto import GetMatchDetailsQuery
from app.core.competition.application.errors import MatchNotFoundError
from app.core.competition.domain.matches import GameType, TeamMatchNoticeCode
from app.core.competition.domain.seasons import SeasonHalf


@pytest.fixture
def details(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'details.db'}")
    statements = []

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    @event.listens_for(engine, "before_cursor_execute")
    def count_queries(_conn, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    try:
        SQLModel.metadata.create_all(engine)
        with Session(engine) as session:
            session.add(
                Season(id=1, start_year=2026, end_year=2027, half=SeasonHalf.VR)
            )
            session.flush()
            session.add(LeagueGroup(id=1, season_id=1, name="Liga", mytt_group_id=1))
            session.flush()
            session.add(
                Team(id=1, season_id=1, league_group_id=1, name="TTC", mytt_team_id=1)
            )
            session.add_all(
                [
                    Member(
                        id=i,
                        first_name=f"Player {i}",
                        last_name="Test",
                        email="private@example.com",
                    )
                    for i in (1, 2, 3)
                ]
            )
            session.flush()
            session.add_all([Player(id=i, member_id=i) for i in (1, 2, 3)])
            session.flush()
            now = datetime(2026, 9, 1, 18, tzinfo=timezone.utc)
            for i in (1, 2, 3):
                session.add(
                    TeamMatch(
                        id=i,
                        team_id=1,
                        opponent_name=f"Gast {i}",
                        is_home=False,
                        play_mode="six",
                        scheduled_at=now,
                        status="finished" if i == 1 else "scheduled",
                        is_completed=i == 1,
                        details_imported_at=now if i == 1 else None,
                        score_ttc=7 if i == 1 else None,
                        score_opponent=3 if i == 1 else None,
                        venue_name="Halle",
                        venue_city="Ort",
                    )
                )
            session.flush()
            session.add(TeamAssignment(team_id=1, player_id=3, position=1))
            session.add_all(
                [
                    MatchLineup(
                        team_match_id=1, player_id=i, position=i, doubles_pair=1
                    )
                    for i in (1, 2)
                ]
            )
            session.add(
                TeamMatchNotice(
                    team_match_id=1, code=TeamMatchNoticeCode.V, info="Verlegt"
                )
            )
            session.add_all(
                [
                    Match(
                        id=1,
                        team_match_id=1,
                        sequence=2,
                        game_type=GameType.SINGLE,
                        match_name="1-1",
                    ),
                    Match(
                        id=2,
                        team_match_id=1,
                        sequence=1,
                        game_type=GameType.DOUBLE,
                        match_name="D1-D1",
                    ),
                    Match(id=3, team_match_id=3, sequence=1, game_type=GameType.SINGLE),
                ]
            )
            session.flush()
            session.add_all(
                [
                    MatchParticipant(match_id=1, player_id=1, opponent_name="Gast A"),
                    MatchParticipant(
                        match_id=2, player_id=1, opponent_name="Gast A / Gast B"
                    ),
                    MatchParticipant(
                        match_id=2, player_id=2, opponent_name="Gast A / Gast B"
                    ),
                    MatchParticipant(match_id=3, player_id=3, opponent_name="Other"),
                ]
            )
            session.add_all(
                [
                    SetResult(
                        match_id=2, set_number=2, points_ttc=12, points_opponent=10
                    ),
                    SetResult(
                        match_id=2, set_number=1, points_ttc=11, points_opponent=8
                    ),
                    SetResult(
                        match_id=1, set_number=1, points_ttc=5, points_opponent=11
                    ),
                ]
            )
            session.commit()
        statements.clear()
        yield build_get_match_details(lambda: Session(engine)), statements
    finally:
        engine.dispose()


def test_complete_details_and_bounded_queries(details):
    usecase, statements = details
    result = usecase.execute(GetMatchDetailsQuery(1))
    assert result.details_available and result.is_completed
    assert result.is_home is False
    assert (result.score_ttc, result.score_opponent) == (7, 3)
    assert result.team_name == "TTC"
    assert result.venue_name == "Halle"
    assert result.notices[0].code == "V"
    assert [entry.player.player_id for entry in result.lineup] == [1, 2]
    assert result.lineup[0].doubles_pair == 1
    assert result.lineup[0].player.first_name == "Player 1"
    assert not hasattr(result.lineup[0].player, "email")
    assert [game.sequence for game in result.games] == [1, 2]
    doubles = result.games[0]
    assert doubles.game_type == "double"
    assert [p.player_id for p in doubles.players] == [1, 2]
    assert doubles.opponent_names == ["Gast A / Gast B"]
    assert [(s.set_number, s.points_ttc, s.points_opponent) for s in doubles.sets] == [
        (1, 11, 8),
        (2, 12, 10),
    ]
    assert len(statements) <= 7  # No additional query per player/game/set.


@pytest.mark.parametrize("match_id", [2, 3])
def test_not_imported_returns_basic_data_and_empty_details(details, match_id):
    usecase, _ = details
    result = usecase.execute(GetMatchDetailsQuery(match_id))
    assert not result.details_available
    assert result.games == [] and result.lineup == []
    assert result.score_ttc is None
    assert result.opponent_name == f"Gast {match_id}"


def test_unknown_match_raises_application_error(details):
    usecase, _ = details
    with pytest.raises(MatchNotFoundError):
        usecase.execute(GetMatchDetailsQuery(999))
