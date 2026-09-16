from unittest.mock import AsyncMock

import pytest
from app.adapters.inbound.http.auth.dependencies import get_current_user
from app.adapters.inbound.http.competition import automation_dependencies as deps
from app.adapters.inbound.http.competition.automation_router import router
from app.core.users.public import UserDetails
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from test_competition_imports import imports  # noqa: F401
from test_match_reload import change_match, job, reloads  # noqa: F401
from test_report_automation import reports  # noqa: F401


@pytest.fixture
def api(reloads):  # noqa: F811
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[deps.provide_sync_matches] = lambda: reloads.overview
    app.dependency_overrides[deps.provide_match_reload] = lambda: reloads.request
    app.dependency_overrides[get_current_user] = lambda: UserDetails(
        id=1, name="Admin", email="admin@example.org", is_active=True, roles=["ADMIN"]
    )
    reloads.competition.meeting.execute = AsyncMock()
    with TestClient(app) as client:
        yield client, app, reloads


def test_get_and_post_contract_and_no_inline_import(api):
    client, _, ctx = api
    response = client.get("/api/admin/mytt/matches")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"imported", "missing_details", "upcoming"}
    match = body["missing_details"][0]
    assert match["id"] == ctx.match_id and match["team_name"] == "TTC I"
    assert match["reload"] is None and match["can_reload"]
    assert job(ctx) is None
    path = f"/api/admin/mytt/matches/{ctx.match_id}/reload"
    response = client.post(path)
    assert response.status_code == 202
    assert response.json()["status"] == "requested"
    assert response.json()["team_match_id"] == ctx.match_id
    assert response.json()["started_at"] is None
    assert client.post(path).json() == response.json()
    match = client.get("/api/admin/mytt/matches").json()["missing_details"][0]
    assert match["reload"] == response.json()
    assert not match["can_reload"]
    ctx.competition.meeting.execute.assert_not_called()


@pytest.mark.parametrize(
    "role,expected", [(None, 401), ("EDITOR", 403), ("MEMBER", 403)]
)
def test_both_endpoints_require_admin(api, role, expected):
    client, app, ctx = api

    def user():
        if role is None:
            raise HTTPException(status_code=401)
        return UserDetails(
            id=2, name="User", email="user@example.org", is_active=True, roles=[role]
        )

    app.dependency_overrides[get_current_user] = user
    assert client.get("/api/admin/mytt/matches").status_code == expected
    assert (
        client.post(f"/api/admin/mytt/matches/{ctx.match_id}/reload").status_code
        == expected
    )
    assert job(ctx) is None


@pytest.mark.parametrize(
    "values,reason",
    [
        ({"is_completed": False}, "abgeschlossen"),
        ({"mytt_meeting_id": None}, "Spiel-ID"),
    ],
)
def test_conflict_responses(api, values, reason):
    client, _, ctx = api
    change_match(ctx, **values)
    response = client.post(f"/api/admin/mytt/matches/{ctx.match_id}/reload")
    assert response.status_code == 409 and reason in response.json()["detail"]
    assert job(ctx) is None


def test_not_found_invalid_id_and_already_imported(api):
    client, _, ctx = api
    assert client.post("/api/admin/mytt/matches/99999/reload").status_code == 404
    assert client.post("/api/admin/mytt/matches/0/reload").status_code == 422
    change_match(ctx, details_imported_at=ctx.clock())
    assert (
        client.post(f"/api/admin/mytt/matches/{ctx.match_id}/reload").status_code == 409
    )
    ctx.competition.meeting.execute.assert_not_called()
