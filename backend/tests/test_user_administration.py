# ruff: noqa: F811 -- imported pytest fixtures are injected by parameter name.
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from app.adapters.inbound.http.users.admin_router import password_router, router
from app.adapters.outbound.mail.password_mail import SmtpPasswordMail
from app.adapters.outbound.persistence.events.models import Event, EventCategory
from app.adapters.outbound.persistence.members.models import Member
from app.adapters.outbound.persistence.users.models import PasswordLink, User
from app.adapters.outbound.security.password_links import SecurePasswordLinkTokens
from app.core.users.application.errors import MailDeliveryError
from sqlmodel import Session, select
from test_identity_http import (  # noqa: F401
    authorization,
    client,
    database,
    login,
    refresh,
)


@pytest.fixture(autouse=True)
def routes(client):
    client.app.include_router(router)
    client.app.include_router(password_router)


def payload(**changes):
    return dict(
        name="New Member",
        email="new@example.org",
        roles=["EDITOR"],
        is_active=True,
        member_id=None,
        member={"first_name": "New", "last_name": "Member"},
        **changes,
    )


@pytest.mark.parametrize("uid", [2, 3, 4])
def test_admin_only(client, uid):
    for method, path, body in [
        ("get", "", None),
        ("get", "/members", None),
        ("get", "/1", None),
        ("get", "/members/1", None),
        ("post", "", payload()),
        ("put", "/4", payload()),
        ("patch", "/4/active", {"is_active": False}),
        ("delete", "/4", None),
        ("post", "/4/password-link", {}),
    ]:
        response = client.request(
            method, "/api/admin/users" + path, json=body, headers=authorization(uid)
        )
        assert response.status_code == 403, response.text


def test_create_list_edit_filter_and_preserve_member_on_delete(client, database):
    response = client.post("/api/admin/users", json=payload(), headers=authorization())
    assert response.status_code == 201, response.text
    uid = response.json()["id"]
    details = client.get(f"/api/admin/users/{uid}", headers=authorization()).json()
    mid = details["member_id"]
    assert details["member"]["first_name"] == "New"
    assert details["roles"] == ["EDITOR"]
    assert "password_hash" not in details
    with Session(database) as session:
        assert session.get(User, uid).password_hash == "!"
    page = client.get(
        "/api/admin/users?search=new&role=EDITOR&active=true", headers=authorization()
    ).json()
    assert page["total"] == 1
    assert page["items"][0]["id"] == uid
    assert (
        client.get("/api/admin/users?limit=1&offset=1", headers=authorization()).json()[
            "total"
        ]
        == 5
    )
    data = payload()
    data.update(member_id=mid, roles=["TEAM_REPORTER"])
    data["member"]["phone"] = "0123"
    assert (
        client.put(
            f"/api/admin/users/{uid}", json=data, headers=authorization()
        ).status_code
        == 204
    )
    assert (
        client.get(f"/api/admin/users/members/{mid}", headers=authorization()).json()[
            "phone"
        ]
        == "0123"
    )
    assert (
        client.delete(f"/api/admin/users/{uid}", headers=authorization()).status_code
        == 204
    )
    with Session(database) as session:
        assert session.get(User, uid) is None
        assert session.get(Member, mid) is not None


def test_existing_member_and_duplicate_protection_are_atomic(client, database):
    with Session(database) as session:
        member = Member(first_name="Existing", last_name="Member")
        session.add(member)
        session.commit()
        mid = member.id
    data = payload()
    data.update(member=None, member_id=mid)
    first = client.post("/api/admin/users", json=data, headers=authorization())
    assert first.status_code == 201
    data["email"] = "other@example.org"
    data["member"] = {"first_name": "Changed", "last_name": "Wrong"}
    assert (
        client.post("/api/admin/users", json=data, headers=authorization()).status_code
        == 409
    )
    with Session(database) as session:
        assert session.get(Member, mid).first_name == "Existing"
        assert (
            session.exec(select(User).where(User.email == "other@example.org")).first()
            is None
        )
    data = payload()
    data["email"] = " NEW@EXAMPLE.ORG "
    assert (
        client.post("/api/admin/users", json=data, headers=authorization()).status_code
        == 409
    )
    assert (
        client.get("/api/admin/users/members", headers=authorization()).json()[0][
            "user_id"
        ]
        == first.json()["id"]
    )


def test_last_admin_protection_in_all_write_routes(client):
    assert (
        client.delete("/api/users/1/roles/ADMIN", headers=authorization()).status_code
        == 409
    )
    assert (
        client.patch(
            "/api/admin/users/1/active",
            json={"is_active": False},
            headers=authorization(),
        ).status_code
        == 409
    )
    assert (
        client.delete("/api/admin/users/1", headers=authorization()).status_code == 409
    )
    data = payload()
    data.update(email="user1@example.org", member=None)
    assert (
        client.put("/api/admin/users/1", json=data, headers=authorization()).status_code
        == 409
    )
    assert (
        client.put("/api/users/4/roles/ADMIN", headers=authorization()).status_code
        == 200
    )
    assert (
        client.delete("/api/users/1/roles/ADMIN", headers=authorization()).status_code
        == 200
    )


def test_system_accounts_hidden_and_immutable(client, database):
    with Session(database) as session:
        session.add(
            User(
                id=10,
                name="System",
                email="system@example.org",
                password_hash="!",
                system_key="test",
            )
        )
        session.commit()
    assert client.get("/api/admin/users", headers=authorization()).json()["total"] == 4
    assert client.get("/api/admin/users/10", headers=authorization()).status_code == 404
    assert (
        client.put("/api/users/10/roles/ADMIN", headers=authorization()).status_code
        == 400
    )
    assert (
        client.delete("/api/admin/users/10", headers=authorization()).status_code == 400
    )


def test_delete_referenced_account_is_blocked(client, database):
    with Session(database) as session:
        category = EventCategory(name="Test", slug="test")
        session.add(category)
        session.flush()
        session.add(
            Event(
                title="Test",
                category_id=category.id,
                created_by_user_id=4,
                starts_at=datetime.now(timezone.utc),
            )
        )
        session.commit()
    response = client.delete("/api/admin/users/4", headers=authorization())
    assert response.status_code == 409, response.text
    with Session(database) as session:
        assert session.get(User, 4) is not None


def issue_link(client, uid=1):
    with (
        patch.object(SmtpPasswordMail, "ensure_configured"),
        patch.object(SmtpPasswordMail, "send") as send,
    ):
        response = client.post(
            f"/api/admin/users/{uid}/password-link", headers=authorization()
        )
        assert response.status_code == 204, response.text
        return send.call_args.args[1]


def test_password_links_expiry_replacement_single_use_and_session_revocation(
    client, database
):
    access, refresh_token = login(client)
    old = issue_link(client)
    token = issue_link(client)
    assert token != old
    with Session(database) as session:
        link = session.exec(select(PasswordLink)).one()
        assert link.token_hash == SecurePasswordLinkTokens().digest(token)
        assert link.token_hash != token
    body = {"token": token, "password": "new-secure-password"}
    assert (
        client.post("/api/auth/set-password", json={**body, "token": old}).status_code
        == 400
    )
    assert (
        client.post(
            "/api/auth/set-password", json={**body, "password": "short"}
        ).status_code
        == 422
    )
    assert client.post("/api/auth/set-password", json=body).status_code == 204
    assert client.post("/api/auth/set-password", json=body).status_code == 400
    assert refresh(client, refresh_token).status_code == 401
    assert (
        client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer " + access.json()["access_token"]},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "user1@example.org", "password": "test-password"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "user1@example.org", "password": body["password"]},
        ).status_code
        == 200
    )
    token = issue_link(client)
    with Session(database) as session:
        link = session.exec(select(PasswordLink)).one()
        link.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.commit()
    assert (
        client.post("/api/auth/set-password", json={**body, "token": token}).status_code
        == 400
    )


def test_deactivation_invalidates_sessions_even_after_reactivation(client, database):
    response = client.post(
        "/api/auth/login",
        json={"email": "user4@example.org", "password": "test-password"},
    )
    token = response.json()["access_token"]
    assert (
        client.patch(
            "/api/admin/users/4/active",
            json={"is_active": False},
            headers=authorization(),
        ).status_code
        == 204
    )
    assert (
        client.patch(
            "/api/admin/users/4/active",
            json={"is_active": True},
            headers=authorization(),
        ).status_code
        == 204
    )
    assert (
        client.get(
            "/api/auth/me", headers={"Authorization": "Bearer " + token}
        ).status_code
        == 401
    )


def test_mail_failure_is_explicit_and_retryable(client):
    with (
        patch.object(SmtpPasswordMail, "ensure_configured"),
        patch.object(
            SmtpPasswordMail,
            "send",
            side_effect=MailDeliveryError("Versand fehlgeschlagen"),
        ),
    ):
        assert (
            client.post(
                "/api/admin/users/4/password-link", headers=authorization()
            ).status_code
            == 503
        )
    assert issue_link(client, 4)


@pytest.mark.parametrize(
    "changes",
    [
        {"email": "invalid"},
        {"name": "  "},
        {"member": {"first_name": "A", "last_name": "B", "birth_date": "2999-01-01"}},
        {
            "member": {
                "first_name": "A",
                "last_name": "B",
                "joined_at": "2026-01-01",
                "membership_end_date": "2025-01-01",
            }
        },
    ],
)
def test_validation(client, changes):
    data = payload()
    data.update(changes)
    assert (
        client.post("/api/admin/users", json=data, headers=authorization()).status_code
        == 422
    )


def test_member_and_account_rollback_on_commit_failure(client, database):
    from app.adapters.outbound.persistence.users.unit_of_work import SqlUserUnitOfWork

    with (
        patch.object(SqlUserUnitOfWork, "commit", side_effect=RuntimeError("failure")),
        pytest.raises(RuntimeError),
    ):
        client.post("/api/admin/users", json=payload(), headers=authorization())
    with Session(database) as session:
        assert session.exec(select(Member)).all() == []
        assert (
            session.exec(select(User).where(User.email == "new@example.org")).first()
            is None
        )


def test_email_change_invalidates_old_link(client):
    token = issue_link(client, 4)
    data = payload()
    data.update(email="changed@example.org", member=None)
    assert (
        client.put("/api/admin/users/4", json=data, headers=authorization()).status_code
        == 204
    )
    assert (
        client.post(
            "/api/auth/set-password",
            json={"token": token, "password": "new-password-long"},
        ).status_code
        == 400
    )


def test_smtp_adapter_sends_fragment_link_and_uses_tls():
    mail = SmtpPasswordMail(
        host="smtp.example.org",
        port=587,
        username="test",
        password="secret",
        sender="club@example.org",
        starttls=True,
        public_url="https://club.example.org",
        lifetime_minutes=60,
    )
    with patch("app.adapters.outbound.mail.password_mail.smtplib.SMTP") as smtp:
        mail.send("member@example.org", "single-use-token")
        connection = smtp.return_value.__enter__.return_value
        connection.starttls.assert_called_once()
        connection.login.assert_called_once_with("test", "secret")
        message = connection.send_message.call_args.args[0]
        assert message["To"] == "member@example.org"
        assert (
            "https://club.example.org/passwort-festlegen#token=single-use-token"
            in message.get_content()
        )


def test_unconfigured_mail_does_not_create_link(client, database):
    with patch.object(
        SmtpPasswordMail,
        "ensure_configured",
        side_effect=MailDeliveryError("SMTP fehlt"),
    ):
        assert (
            client.post(
                "/api/admin/users/4/password-link", headers=authorization()
            ).status_code
            == 503
        )
    with Session(database) as session:
        assert session.exec(select(PasswordLink)).all() == []
