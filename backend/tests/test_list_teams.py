"""Exercise ListTeams through bootstrap and the real SQL reader."""

import pytest
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

import app.model_registry  # noqa: F401
from app.adapters.outbound.persistence.competition.leagues import LeagueGroup
from app.adapters.outbound.persistence.competition.seasons import Season
from app.adapters.outbound.persistence.competition.teams import Team
from app.bootstrap.competition import build_list_teams
from app.core.competition.application.dto import ListTeamsQuery, TeamSummary
from app.core.competition.domain.seasons import SeasonHalf


@pytest.fixture
def list_teams(tmp_path):
    # Each test gets its own database, independent of backend/.env.
    engine = create_engine(f"sqlite:///{tmp_path / 'teams.db'}")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    try:
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
            # IDs deliberately differ from the expected category/number order.
            for team_id, season_id, name, number, category in [
                (1, 1, "Jugend 15", 1, "J15"),
                (2, 1, "Herren II", 2, "H"),
                (3, 1, "Herren I", 1, "H"),
                (4, 2, "Herren Rueckrunde", 1, "H"),
                (5, 2, "Ohne Kategorie", None, None),
            ]:
                session.add(
                    Team(
                        id=team_id,
                        season_id=season_id,
                        league_group_id=season_id,
                        mytt_team_id=team_id,
                        name=name,
                        team_number=number,
                        category=category,
                    )
                )
            session.commit()
        yield build_list_teams(session_factory=lambda: Session(engine))
    finally:
        engine.dispose()


def test_lists_all_categories_in_selected_season_in_order(list_teams):
    result = list_teams.execute(ListTeamsQuery(season_id=1))

    assert result == [
        TeamSummary(id=3, name="Herren I", team_number=1, category="H"),
        TeamSummary(id=2, name="Herren II", team_number=2, category="H"),
        TeamSummary(id=1, name="Jugend 15", team_number=1, category="J15"),
    ]


def test_filters_category_and_season(list_teams):
    result = list_teams.execute(ListTeamsQuery(season_id=1, category="H"))

    assert [team.id for team in result] == [3, 2]


@pytest.mark.parametrize(
    "query",
    [
        ListTeamsQuery(season_id=999),
        ListTeamsQuery(season_id=1, category="J19"),
    ],
)
def test_returns_empty_list_when_nothing_matches(list_teams, query):
    assert list_teams.execute(query) == []


def test_keeps_teams_without_category_or_number(list_teams):
    result = list_teams.execute(ListTeamsQuery(season_id=2))

    # NULL ordering differs between SQLite and PostgreSQL; no promise about it yet.
    assert {team.id for team in result} == {4, 5}
    assert (
        TeamSummary(id=5, name="Ohne Kategorie", team_number=None, category=None)
        in result
    )
