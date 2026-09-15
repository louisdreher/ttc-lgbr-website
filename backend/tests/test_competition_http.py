from datetime import date, datetime, timezone
from unittest.mock import Mock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.adapters.inbound.http.auth.dependencies import get_current_user
from app.adapters.inbound.http.competition import dependencies as deps
from app.adapters.inbound.http.competition.router import router
from app.core.competition.application import dto
from app.core.competition.application.errors import (
    MatchNotFoundError,
    TeamNotFoundError,
)
from app.core.competition.domain.seasons import SeasonHalf
from app.core.users.public import UserDetails


@pytest.fixture
def api():
    app = FastAPI()
    app.include_router(router)
    cases = {}

    def override(case):
        def provide():
            return case

        return provide

    for name in (
        "list_seasons",
        "list_teams",
        "get_schedule",
        "get_team_standings",
        "get_match_details",
        "get_team_lineup",
    ):
        case = Mock()
        case.execute.return_value = []
        cases[name] = case
        app.dependency_overrides[getattr(deps, "provide_" + name)] = override(case)

    def anonymous():
        raise HTTPException(status_code=401, detail="Nicht authentifiziert")

    app.dependency_overrides[get_current_user] = anonymous
    with TestClient(app) as client:
        yield client, app, cases


def test_public_seasons_teams_and_schedule(api):
    client, _, cases = api
    cases["list_seasons"].execute.return_value = [
        dto.SeasonSummary(1, 2026, 2027, SeasonHalf.VR)
    ]
    assert client.get("/api/competition/seasons").json() == [
        {"id": 1, "start_year": 2026, "end_year": 2027, "half": "vr"}
    ]
    cases["list_teams"].execute.return_value = [dto.TeamSummary(2, "TTC", 1, "H")]
    response = client.get("/api/competition/teams?season_id=1&category=H")
    assert response.status_code == 200
    assert response.json()[0]["name"] == "TTC"
    cases["list_teams"].execute.assert_called_once_with(dto.ListTeamsQuery(1, "H"))
    response = client.get(
        "/api/competition/schedule?date_from=2026-09-01&date_to=2026-09-30&team_ids=2&team_ids=3&category=H"
    )
    assert response.status_code == 200
    cases["get_schedule"].execute.assert_called_once_with(
        dto.GetScheduleQuery(date(2026, 9, 1), date(2026, 9, 30), (2, 3), "H")
    )
    assert client.get("/api/competition/teams/2/standings").json() == []
    cases["get_team_standings"].execute.assert_called_once_with(
        dto.GetTeamStandingsQuery(2)
    )


@pytest.mark.parametrize(
    "url",
    [
        "/teams",
        "/teams?season_id=0",
        "/matches/-1",
        "/teams/0/standings",
        "/schedule?date_from=bad&date_to=2026-09-30",
        "/schedule?date_from=2026-10-01&date_to=2026-09-30",
        "/schedule?date_from=2026-09-01&date_to=2026-09-30&team_ids=0",
    ],
)
def test_validation(api, url):
    client, _, cases = api
    assert client.get("/api/competition" + url).status_code == 422
    for case in cases.values():
        case.execute.assert_not_called()


def test_match_details_nested_response_and_not_found(api):
    client, _, cases = api
    cases["get_match_details"].execute.return_value = dto.MatchDetails(
        id=5,
        team_id=2,
        team_name="TTC",
        opponent_name="Gast",
        is_home=False,
        scheduled_at=datetime(2026, 9, 1, 18, tzinfo=timezone.utc),
        original_scheduled_at=None,
        started_at=None,
        ended_at=None,
        status="finished",
        is_completed=True,
        score_ttc=7,
        score_opponent=3,
        play_mode=None,
        venue_name=None,
        venue_street=None,
        venue_city=None,
        details_available=True,
        games=[
            dto.MatchGame(
                10,
                1,
                "single",
                "1-1",
                [dto.MatchPlayer(8, "Anna", "A")],
                ["Gast A"],
                [dto.MatchSet(1, 11, 8)],
            )
        ],
    )
    response = client.get("/api/competition/matches/5")
    assert response.status_code == 200
    assert response.json()["games"][0]["sets"][0]["points_ttc"] == 11
    assert response.json()["games"][0]["players"][0] == {
        "player_id": 8,
        "first_name": "Anna",
        "last_name": "A",
    }
    cases["get_match_details"].execute.side_effect = MatchNotFoundError(99)
    assert client.get("/api/competition/matches/99").status_code == 404


def test_lineup_requires_admin(api):
    client, app, cases = api
    endpoint = "/api/competition/teams/2/lineup"
    assert client.get(endpoint).status_code == 401
    app.dependency_overrides[get_current_user] = lambda: UserDetails(
        id=1,
        email="editor@example.com",
        name="Editor",
        is_active=True,
        roles=["EDITOR"],
    )
    assert client.get(endpoint).status_code == 403
    cases["get_team_lineup"].execute.assert_not_called()
    app.dependency_overrides[get_current_user] = lambda: UserDetails(
        id=1, email="admin@example.com", name="Admin", is_active=True, roles=["ADMIN"]
    )
    cases["get_team_lineup"].execute.return_value = dto.TeamLineup(
        2, "TTC", 1, "H", [dto.TeamLineupEntry(8, "Anna", "A", 1, "Ersatzspieler")]
    )
    response = client.get(endpoint)
    assert response.status_code == 200
    assert response.json()["players"][0]["status"] == "Ersatzspieler"
    cases["get_team_lineup"].execute.side_effect = TeamNotFoundError(2)
    assert client.get(endpoint).status_code == 404


def test_routes_registered_in_main():
    from app.main import app

    paths = app.openapi()["paths"]
    for path in (
        "seasons",
        "teams",
        "schedule",
        "teams/{team_id}/standings",
        "teams/{team_id}/lineup",
        "matches/{match_id}",
    ):
        assert "get" in paths["/api/competition/" + path]
