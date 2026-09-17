from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import app.model_registry  # noqa: F401 -- register FK targets
from app.adapters.inbound.http.articles.admin_router import router as articles_router
from app.adapters.inbound.http.auth.router import router as auth_router
from app.adapters.inbound.http.events.admin_router import router as events_router
from app.adapters.inbound.http.users.router import router as users_router
from app.adapters.outbound.persistence.auth.models import RefreshSession
from app.adapters.outbound.persistence.auth.repository import (
    SqlRefreshSessionRepository,
)
from app.adapters.outbound.persistence.database import get_session
from app.adapters.outbound.persistence.users.models import Role, User
from app.adapters.outbound.persistence.users.unit_of_work import SqlUserUnitOfWork
from app.adapters.outbound.security.passwords import ArgonPasswords
from app.adapters.outbound.security.tokens import JwtTokens
from app.bootstrap.auth import build_tokens
from app.bootstrap.settings import settings
from app.bootstrap.users import build_create_user, build_ensure_default_roles
from app.core.users.application.dto import CreateUserCommand


@pytest.fixture
def database():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        build_ensure_default_roles(session).execute()
        roles = {role.name: role for role in session.exec(select(Role)).all()}
        password_hash = ArgonPasswords().hash("test-password")
        for number, role_name in enumerate(
            ("ADMIN", "EDITOR", "TEAM_REPORTER", None), start=1
        ):
            session.add(
                User(
                    id=number,
                    email=f"user{number}@example.org",
                    name=f"User {number}",
                    password_hash=password_hash,
                    roles=[roles[role_name]] if role_name else [],
                )
            )
        session.commit()
    yield engine
    engine.dispose()


@pytest.fixture
def client(database):
    app = FastAPI()
    for router in (auth_router, users_router, events_router, articles_router):
        app.include_router(router)

    def session_dependency():
        with Session(database) as session:
            yield session

    app.dependency_overrides[get_session] = session_dependency
    with TestClient(app) as client:
        yield client


def authorization(user_id=1):
    return {
        "Authorization": "Bearer "
        + build_tokens().issue_access(user_id, datetime.now(timezone.utc))
    }


def login(client):
    response = client.post(
        "/api/auth/login",
        json={"email": " USER1@EXAMPLE.ORG ", "password": "test-password"},
    )
    assert response.status_code == 200, response.text
    return response, response.cookies.get(settings.refresh_cookie_name)


def refresh(client, token):
    return client.post(
        "/api/auth/refresh",
        headers={"cookie": f"{settings.refresh_cookie_name}={token}"},
    )


def test_login_me_cookie_and_hashed_refresh_storage(client, database):
    response, raw = login(client)
    assert set(response.json()) == {"access_token", "token_type"}
    assert response.json()["token_type"] == "bearer"
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert f"Path={settings.cookie_path}" in cookie
    assert f"SameSite={settings.cookie_samesite}" in cookie
    assert f"Max-Age={settings.refresh_token_expire_days * 86400}" in cookie
    me = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer " + response.json()["access_token"]},
    )
    assert me.json() == {
        "id": 1,
        "email": "user1@example.org",
        "name": "User 1",
        "is_active": True,
        "roles": ["ADMIN"],
    }
    with Session(database) as session:
        stored = session.exec(select(RefreshSession)).one()
        assert stored.token_hash == build_tokens().hash_refresh(raw)
        assert stored.token_hash != raw
    assert raw not in response.text
    assert "password_hash" not in me.text


@pytest.mark.parametrize(
    "email,password",
    [("missing@example.org", "test-password"), ("user1@example.org", "wrong")],
)
def test_bad_login_does_not_create_session(client, database, email, password):
    response = client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "E-Mail oder Passwort ist falsch"
    with Session(database) as session:
        assert session.exec(select(RefreshSession)).all() == []


def test_refresh_rotates_and_replay_revokes_family_but_not_other_login(
    client, database
):
    _, first = login(client)
    _, independent = login(client)
    response = refresh(client, first)
    assert response.status_code == 200, response.text
    second = response.cookies.get(settings.refresh_cookie_name)
    assert first != second
    with Session(database) as session:
        old = session.exec(
            select(RefreshSession).where(
                RefreshSession.token_hash == build_tokens().hash_refresh(first)
            )
        ).one()
        new = session.exec(
            select(RefreshSession).where(
                RefreshSession.token_hash == build_tokens().hash_refresh(second)
            )
        ).one()
        assert old.used_at is not None
        assert old.family_id == new.family_id
    assert refresh(client, first).status_code == 401
    assert refresh(client, second).status_code == 401
    assert refresh(client, independent).status_code == 200
    with Session(database) as session:
        old = session.exec(
            select(RefreshSession).where(
                RefreshSession.token_hash == build_tokens().hash_refresh(first)
            )
        ).one()
        assert all(
            row.revoked_at is not None
            for row in session.exec(
                select(RefreshSession).where(RefreshSession.family_id == old.family_id)
            ).all()
        )


def test_rotation_failure_rolls_back_consumption_and_new_token(client, database):
    _, token = login(client)
    save = SqlRefreshSessionRepository.save
    calls = 0

    def fail_after_new_token(repository, entity):
        nonlocal calls
        save(repository, entity)
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated persistence failure")

    with (
        patch.object(SqlRefreshSessionRepository, "save", fail_after_new_token),
        pytest.raises(RuntimeError),
    ):
        refresh(client, token)
    with Session(database) as session:
        rows = session.exec(select(RefreshSession)).all()
        assert len(rows) == 1
        assert rows[0].used_at is None
    assert refresh(client, token).status_code == 200


def test_signing_failure_rolls_back_login_session(client, database):
    with (
        patch.object(
            JwtTokens, "issue_access", side_effect=RuntimeError("signing failed")
        ),
        pytest.raises(RuntimeError),
    ):
        client.post(
            "/api/auth/login",
            json={"email": "user1@example.org", "password": "test-password"},
        )
    with Session(database) as session:
        assert session.exec(select(RefreshSession)).all() == []


def test_logout_clears_cookie_and_revokes_rotated_family(client):
    _, first = login(client)
    second = refresh(client, first).cookies.get(settings.refresh_cookie_name)
    response = client.post(
        "/api/auth/logout",
        headers={"cookie": f"{settings.refresh_cookie_name}={first}"},
    )
    assert response.status_code == 204
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert f"Path={settings.cookie_path}" in response.headers["set-cookie"]
    assert refresh(client, second).status_code == 401
    assert client.post("/api/auth/logout").status_code == 204


def test_missing_unknown_and_expired_refresh_are_rejected(client, database):
    assert client.post("/api/auth/refresh").status_code == 401
    assert refresh(client, "unknown").status_code == 401
    _, raw = login(client)
    with Session(database) as session:
        row = session.exec(select(RefreshSession)).one()
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.commit()
    assert refresh(client, raw).json()["detail"] == "Session ist abgelaufen"


def test_deactivated_user_cannot_login_refresh_or_access_me(client, database):
    response, raw = login(client)
    with Session(database) as session:
        session.get(User, 1).is_active = False
        session.commit()
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "user1@example.org", "password": "test-password"},
        ).status_code
        == 401
    )
    assert refresh(client, raw).status_code == 401
    assert (
        client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer " + response.json()["access_token"]},
        ).status_code
        == 401
    )


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer invalid"}, {"Authorization": "Basic invalid"}],
)
def test_missing_or_invalid_access_token_returns_bearer_challenge(client, headers):
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_expired_access_token_is_rejected(client):
    token = build_tokens().issue_access(
        1, datetime.now(timezone.utc) - timedelta(days=1)
    )
    assert (
        client.get(
            "/api/auth/me", headers={"Authorization": "Bearer " + token}
        ).status_code
        == 401
    )


def test_admin_creates_user_without_leaking_password_or_assigning_roles(
    client, database
):
    response = client.post(
        "/api/users/",
        headers=authorization(),
        json={
            "email": " NEW@EXAMPLE.ORG ",
            "name": " New ",
            "password": "new-password",
            "roles": ["ADMIN"],
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data == {
        "id": 5,
        "email": "new@example.org",
        "name": "New",
        "is_active": True,
        "roles": [],
    }
    with Session(database) as session:
        user = session.get(User, data["id"])
        assert user.password_hash != "new-password"
        assert ArgonPasswords().verify("new-password", user.password_hash)
    assert (
        client.post(
            "/api/users/",
            headers=authorization(),
            json={"email": "new@example.org", "name": "X", "password": "X"},
        ).status_code
        == 409
    )


@pytest.mark.parametrize("user_id", [2, 3, 4])
def test_only_admin_may_create_users_or_change_roles(client, user_id):
    assert (
        client.post(
            "/api/users/",
            headers=authorization(user_id),
            json={"email": "new@example.org", "name": "New", "password": "test"},
        ).status_code
        == 403
    )
    assert (
        client.put(
            "/api/users/4/roles/ADMIN", headers=authorization(user_id)
        ).status_code
        == 403
    )
    assert (
        client.delete(
            "/api/users/1/roles/ADMIN", headers=authorization(user_id)
        ).status_code
        == 403
    )


def test_role_assignment_and_removal_are_idempotent_and_visible_on_next_request(client):
    for _ in range(2):
        assert (
            client.put("/api/users/4/roles/EDITOR", headers=authorization()).status_code
            == 200
        )
    assert client.get("/api/auth/me", headers=authorization(4)).json()["roles"] == [
        "EDITOR"
    ]
    for _ in range(2):
        assert (
            client.delete(
                "/api/users/4/roles/EDITOR", headers=authorization()
            ).status_code
            == 200
        )
    assert client.get("/api/auth/me", headers=authorization(4)).json()["roles"] == []
    assert (
        client.put("/api/users/999/roles/EDITOR", headers=authorization()).status_code
        == 404
    )


@pytest.mark.parametrize("user_id,expected", [(1, 200), (2, 200), (3, 403), (4, 403)])
def test_existing_event_permissions_still_use_current_roles(client, user_id, expected):
    assert (
        client.get("/api/admin/events", headers=authorization(user_id)).status_code
        == expected
    )


@pytest.mark.parametrize("user_id,expected", [(1, 201), (2, 201), (3, 201), (4, 403)])
def test_article_writing_allows_admin_editor_and_reporter(
    client, user_id, expected
):
    response = client.post(
        "/api/admin/articles",
        headers=authorization(user_id),
        json={"title": "Test", "slug": "test", "teaser": "Test", "content": "Test"},
    )
    assert response.status_code == expected, response.text


def test_user_commit_failure_rolls_back_hash_and_user(database):
    with Session(database) as session:
        use_case = build_create_user(session)
        with (
            patch.object(
                SqlUserUnitOfWork, "commit", side_effect=RuntimeError("commit failed")
            ),
            pytest.raises(RuntimeError),
        ):
            use_case.execute(
                CreateUserCommand(email="new@example.org", name="New", password="test")
            )
    with Session(database) as session:
        assert (
            session.exec(select(User).where(User.email == "new@example.org")).all()
            == []
        )


def test_default_roles_remain_idempotent(database):
    with Session(database) as session:
        build_ensure_default_roles(session).execute()
        build_ensure_default_roles(session).execute()
        assert sorted(role.name for role in session.exec(select(Role)).all()) == [
            "ADMIN",
            "EDITOR",
            "TEAM_REPORTER",
        ]
