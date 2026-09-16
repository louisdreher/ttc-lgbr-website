from dataclasses import asdict
from unittest.mock import Mock
from uuid import uuid4

import pytest
from app.adapters.inbound.http.auth.dependencies import get_current_user
from app.adapters.inbound.http.competition import automation_dependencies as deps
from app.adapters.inbound.http.competition.automation_router import router
from app.core.competition.application.sync.automation.commands import (
    RequestSync,
    UpdateSyncSettings,
)
from app.core.users.public import UserDetails
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from test_sync_automation import automation  # noqa: F401


@pytest.fixture
def api(automation):  # noqa: F811
    _, uow, _, _, _, status = automation
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[deps.provide_sync_status] = lambda: status
    app.dependency_overrides[deps.provide_sync_settings] = lambda: UpdateSyncSettings(
        uow
    )
    app.dependency_overrides[deps.provide_sync_request] = lambda: RequestSync(uow)
    outbox, retry = Mock(), Mock()
    outbox.execute.return_value = []
    app.dependency_overrides[deps.provide_outbox_status] = lambda: outbox
    app.dependency_overrides[deps.provide_outbox_retry] = lambda: retry
    app.dependency_overrides[get_current_user] = lambda: UserDetails(
        id=1, email="admin@example.org", name="Admin", is_active=True, roles=["ADMIN"]
    )
    with TestClient(app) as client:
        yield client, app, status, outbox, retry


def test_settings_status_and_async_request(api):
    client, _, status, _, _ = api
    response = client.get("/api/admin/mytt/status")
    assert response.status_code == 200
    assert response.json()["worker_online"] is False
    settings = client.get("/api/admin/mytt/settings").json()
    settings.update(nightly_hour=4, result_delay_minutes=210)
    assert client.put("/api/admin/mytt/settings", json=settings).json() == settings
    assert client.post("/api/admin/mytt/sync").status_code == 202
    assert status.execute().state.requested
    assert (
        status.execute().state.last_run is None
    )  # HTTP never performs the external sync
    assert client.get("/api/admin/mytt/outbox").json() == []


@pytest.mark.parametrize(
    "role,expected", [(None, 401), ("EDITOR", 403), ("MEMBER", 403)]
)
def test_all_routes_require_admin(api, role, expected):
    client, app, status, outbox, retry = api

    def user():
        if role is None:
            raise HTTPException(status_code=401)
        return UserDetails(
            id=2, email="user@example.org", name="User", is_active=True, roles=[role]
        )

    app.dependency_overrides[get_current_user] = user
    for method, path, body in [
        ("GET", "/status", None),
        ("GET", "/settings", None),
        ("PUT", "/settings", asdict(status.execute().settings)),
        ("POST", "/sync", None),
        ("GET", "/outbox", None),
        ("POST", f"/outbox/{uuid4()}/retry", None),
    ]:
        assert (
            client.request(method, "/api/admin/mytt" + path, json=body).status_code
            == expected
        )
    assert not status.execute().state.requested
    outbox.execute.assert_not_called()
    retry.execute.assert_not_called()


def test_validation_and_retry_conflict(api):
    client, _, _, _, retry = api
    assert (
        client.put(
            "/api/admin/mytt/settings", json={"result_retry_minutes": 0}
        ).status_code
        == 422
    )
    assert (
        client.put("/api/admin/mytt/settings", json={"unknown": True}).status_code
        == 422
    )
    assert client.get("/api/admin/mytt/outbox?limit=0").status_code == 422
    retry.execute.side_effect = ValueError("Nachricht wird gerade verarbeitet.")
    assert client.post(f"/api/admin/mytt/outbox/{uuid4()}/retry").status_code == 409
