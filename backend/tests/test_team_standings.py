import pytest
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

import app.model_registry  # noqa: F401
from app.adapters.outbound.persistence.competition.leagues import (
    LeagueGroup,
    LeagueTableEntry,
)
from app.adapters.outbound.persistence.competition.seasons import Season
from app.adapters.outbound.persistence.competition.teams import Team
from app.bootstrap.competition import build_get_team_standings
from app.core.competition.application.dto import GetTeamStandingsQuery, StandingSummary
from app.core.competition.domain.seasons import SeasonHalf


@pytest.fixture
def standings(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'standings.db'}")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
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
                    LeagueGroup(
                        id=i, season_id=2 if i == 2 else 1, mytt_group_id=i, name="Liga"
                    )
                    for i in (1, 2, 3)
                ]
            )
            session.flush()
            session.add_all(
                [
                    Team(
                        id=i,
                        season_id=2 if i == 2 else 1,
                        league_group_id=i,
                        mytt_team_id=100,
                        name="TTC",
                    )
                    for i in (1, 2)
                ]
            )
            session.add(
                Team(
                    id=3,
                    season_id=1,
                    league_group_id=3,
                    mytt_team_id=300,
                    name="Ohne Tabelle",
                )
            )
            session.add(
                Team(
                    id=4,
                    season_id=1,
                    league_group_id=1,
                    mytt_team_id=200,
                    name="Zweite Mannschaft",
                )
            )
            session.flush()
            for entry_id, group_id, external_id, name, position in [
                (1, 1, 100, "TTC", 2),
                (2, 1, 200, "Gast", 1),
                (3, 2, 100, "Andere Saison", 1),
            ]:
                session.add(
                    LeagueTableEntry(
                        id=entry_id,
                        league_group_id=group_id,
                        mytt_team_id=external_id,
                        club_id="club",
                        team_name=name,
                        position=position,
                        meetings_count=3,
                        meetings_won=2,
                        meetings_tie=0,
                        meetings_lost=1,
                        points_won=4,
                        points_lost=2,
                        matches_won=20,
                        matches_lost=10,
                        sets_won=60,
                        sets_lost=35,
                        games_won=900,
                        games_lost=800,
                    )
                )
            session.commit()
        yield build_get_team_standings(lambda: Session(engine))
    finally:
        engine.dispose()


def test_complete_group_table_sorted_with_selected_team(standings):
    rows = standings.execute(GetTeamStandingsQuery(team_id=1))
    assert [row.team_name for row in rows] == ["Gast", "TTC"]
    assert rows[0].is_selected_team is False
    assert rows[1] == StandingSummary(
        team_name="TTC",
        position=2,
        is_selected_team=True,
        meetings_count=3,
        meetings_won=2,
        meetings_tie=0,
        meetings_lost=1,
        points_won=4,
        points_lost=2,
        matches_won=20,
        matches_lost=10,
        sets_won=60,
        sets_lost=35,
        games_won=900,
        games_lost=800,
    )


def test_same_external_team_id_in_other_season_stays_separate(standings):
    rows = standings.execute(GetTeamStandingsQuery(team_id=2))
    assert len(rows) == 1
    assert rows[0].team_name == "Andere Saison"
    assert rows[0].is_selected_team is True


def test_second_team_in_same_group_changes_highlight(standings):
    rows = standings.execute(GetTeamStandingsQuery(team_id=4))
    assert [row.is_selected_team for row in rows] == [True, False]


@pytest.mark.parametrize("team_id", [3, 999])
def test_missing_table_or_unknown_team_returns_empty(standings, team_id):
    assert standings.execute(GetTeamStandingsQuery(team_id=team_id)) == []
