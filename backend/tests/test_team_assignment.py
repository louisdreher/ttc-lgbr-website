import pytest
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

import app.model_registry  # noqa: F401
from app.adapters.outbound.persistence.competition.leagues import LeagueGroup
from app.adapters.outbound.persistence.competition.repository import (
    SqlCompetitionRepository,
)
from app.adapters.outbound.persistence.competition.seasons import Season
from app.adapters.outbound.persistence.competition.teams import Team, TeamMembership
from app.adapters.outbound.persistence.members.models import Member, Player
from app.bootstrap.competition import build_assign_player_to_team
from app.core.competition.application.dto import AssignPlayerToTeamCommand
from app.core.competition.application.errors import (
    PlayerNotFoundError,
    TeamNotFoundError,
)
from app.core.competition.domain.seasons import SeasonHalf
from app.core.competition.domain.teams import AssignmentRankingError, AssignmentStatus


@pytest.fixture
def database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'assignments.db'}")

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                Season(id=1, start_year=2026, end_year=2027, half=SeasonHalf.VR),
                Season(id=2, start_year=2026, end_year=2027, half=SeasonHalf.RR),
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
                    season_id=1 if i < 3 else 2,
                    league_group_id=1 if i < 3 else 2,
                    mytt_team_id=i,
                    name=f"Team {i}",
                    category="H",
                    team_number=i,
                )
                for i in (1, 2, 3)
            ]
        )
        session.add_all(
            [Member(id=i, first_name=str(i), last_name="Test") for i in range(1, 5)]
        )
        session.flush()
        session.add_all([Player(id=i, member_id=i) for i in range(1, 5)])
        session.flush()
        session.add_all(
            [
                TeamMembership(team_id=1, player_id=1, rank="10"),
                TeamMembership(team_id=1, player_id=2, rank="2"),
                TeamMembership(team_id=2, player_id=3, rank="1"),
                TeamMembership(team_id=3, player_id=1, rank="9"),
                TeamMembership(team_id=3, player_id=4, rank="1"),
            ]
        )
        session.commit()
    yield engine
    engine.dispose()


def lineup(engine):
    with Session(engine) as session:
        team = SqlCompetitionRepository(session).get_team(1)
        return sorted(
            [(item.player_id, item.position, item.status) for item in team.assignments],
            key=lambda item: item[1],
        )


def test_assign_reorders_and_updates_status(database):
    usecase = build_assign_player_to_team(lambda: Session(database))
    for player_id in (3, 1, 2):
        usecase.execute(AssignPlayerToTeamCommand(1, player_id))
    assert lineup(database) == [(2, 1, None), (1, 2, None), (3, 3, None)]
    usecase.execute(AssignPlayerToTeamCommand(1, 1, AssignmentStatus.SUBSTITUTE))
    assert lineup(database) == [(2, 1, None), (1, 2, "Ersatzspieler"), (3, 3, None)]
    usecase.execute(AssignPlayerToTeamCommand(1, 1))
    assert lineup(database)[1] == (1, 2, None)


@pytest.mark.parametrize(
    ("team_id", "player_id", "error"),
    [
        (99, 1, TeamNotFoundError),
        (1, 99, PlayerNotFoundError),
        (1, 4, AssignmentRankingError),
    ],
)
def test_invalid_assignment_does_not_write(database, team_id, player_id, error):
    usecase = build_assign_player_to_team(lambda: Session(database))
    with pytest.raises(error):
        usecase.execute(AssignPlayerToTeamCommand(team_id, player_id))
    assert lineup(database) == []


@pytest.mark.parametrize("rank", [None, "invalid", "0", "10"])
def test_bad_or_duplicate_rank_preserves_existing_lineup(database, rank):
    usecase = build_assign_player_to_team(lambda: Session(database))
    usecase.execute(AssignPlayerToTeamCommand(1, 1))
    with Session(database) as session:
        membership = session.get(TeamMembership, (1, 2))
        membership.rank = rank
        session.add(membership)
        session.commit()
    with pytest.raises(AssignmentRankingError):
        usecase.execute(AssignPlayerToTeamCommand(1, 2))
    assert lineup(database) == [(1, 1, None)]


def test_conflicting_memberships_and_invalid_status(database):
    usecase = build_assign_player_to_team(lambda: Session(database))
    with Session(database) as session:
        session.add(TeamMembership(team_id=2, player_id=1, rank="5"))
        session.commit()
    with pytest.raises(AssignmentRankingError):
        usecase.execute(AssignPlayerToTeamCommand(1, 1))
    with pytest.raises(ValueError):
        usecase.execute(AssignPlayerToTeamCommand(1, 2, "unknown"))
    assert lineup(database) == []


def test_other_category_does_not_affect_order(database):
    with Session(database) as session:
        session.add(
            Team(
                id=4,
                season_id=1,
                league_group_id=1,
                mytt_team_id=4,
                name="Jugend",
                category="J15",
                team_number=1,
            )
        )
        session.flush()
        session.add_all(
            [
                TeamMembership(team_id=4, player_id=1, rank="1"),
                TeamMembership(team_id=4, player_id=4, rank="2"),
            ]
        )
        session.commit()
    usecase = build_assign_player_to_team(lambda: Session(database))
    usecase.execute(AssignPlayerToTeamCommand(1, 1))
    usecase.execute(AssignPlayerToTeamCommand(1, 2))
    assert lineup(database) == [(2, 1, None), (1, 2, None)]
    with pytest.raises(AssignmentRankingError):
        usecase.execute(AssignPlayerToTeamCommand(1, 4))


def test_historical_manual_insert_move_and_status(database):
    with Session(database) as session:
        team = session.get(Team, 1)
        team.category = None
        session.add(team)
        session.commit()
    usecase = build_assign_player_to_team(lambda: Session(database))
    with pytest.raises(AssignmentRankingError, match="Kategorie"):
        usecase.execute(AssignPlayerToTeamCommand(1, 1))
    usecase.execute(AssignPlayerToTeamCommand(1, 4, position=1))
    usecase.execute(AssignPlayerToTeamCommand(1, 1, position=1))
    assert lineup(database) == [(1, 1, None), (4, 2, None)]
    usecase.execute(
        AssignPlayerToTeamCommand(1, 4, AssignmentStatus.SUBSTITUTE, position=1)
    )
    assert lineup(database) == [(4, 1, "Ersatzspieler"), (1, 2, None)]


@pytest.mark.parametrize("position", [0, -1, 3, True, 1.5])
def test_invalid_manual_position_is_atomic(database, position):
    usecase = build_assign_player_to_team(lambda: Session(database))
    usecase.execute(AssignPlayerToTeamCommand(1, 1, position=1))
    with pytest.raises(AssignmentRankingError):
        usecase.execute(AssignPlayerToTeamCommand(1, 2, position=position))
    assert lineup(database) == [(1, 1, None)]


def test_automatic_assignment_replaces_manual_order(database):
    usecase = build_assign_player_to_team(lambda: Session(database))
    usecase.execute(AssignPlayerToTeamCommand(1, 3, position=1))
    usecase.execute(AssignPlayerToTeamCommand(1, 1, position=2))
    usecase.execute(AssignPlayerToTeamCommand(1, 2))
    assert lineup(database) == [(2, 1, None), (1, 2, None), (3, 3, None)]
