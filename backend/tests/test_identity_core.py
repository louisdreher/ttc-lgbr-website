import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.core.auth.application.commands import Login
from app.core.auth.application.dto import LoginCommand
from app.core.auth.domain.session import (
    AuthenticationError,
    RefreshSession,
    SessionReusedError,
)
from app.core.users.domain.user import Role, User
from app.core.users.public import UserCredentials


def test_user_normalizes_identity_and_changes_roles_idempotently():
    user = User.create(email=" A@Example.org ", name=" Alice ", password_hash="secret")
    role = Role(id=1, name="ADMIN")
    user.add_role(role)
    user.add_role(role)
    assert (user.email, user.name, user.roles) == ("a@example.org", "Alice", [role])
    user.remove_role(role)
    user.remove_role(role)
    assert user.roles == []
    assert "secret" not in repr(user)


@pytest.mark.parametrize("state", ["expired", "revoked", "used"])
def test_invalid_session_cannot_be_consumed(state):
    now = datetime.now(timezone.utc)
    session = RefreshSession(
        user_id=1, token_hash="secret", expires_at=now + timedelta(days=1)
    )
    if state == "expired":
        session.expires_at = now
    elif state == "revoked":
        session.revoked_at = now
    else:
        session.used_at = now - timedelta(minutes=1)
    previous = session.used_at
    with pytest.raises(SessionReusedError if state == "used" else AuthenticationError):
        session.use(now)
    assert session.used_at == previous


def test_login_uses_injected_ports_without_database_or_http():
    class MemoryUnitOfWork:
        def __init__(self):
            self.saved = []
            self.sessions = SimpleNamespace(save=self.saved.append)
            self.committed = False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def commit(self):
            self.committed = True

    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    uow = MemoryUnitOfWork()
    users = Mock()
    users.get_credentials.return_value = UserCredentials(
        user_id=7, is_active=True, password_hash="hash"
    )
    passwords = Mock()
    passwords.verify.return_value = True
    tokens = Mock()
    tokens.new_refresh.return_value = "refresh"
    tokens.hash_refresh.return_value = "refresh-hash"
    tokens.issue_access.return_value = "access"
    result = Login(
        uow, users, passwords, tokens, timedelta(days=2), lambda: now
    ).execute(LoginCommand(email="alice@example.org", password="password"))
    passwords.verify.assert_called_once_with("password", "hash")
    tokens.issue_access.assert_called_once_with(7, now)
    assert uow.committed
    assert len(uow.saved) == 1
    assert uow.saved[0].token_hash == "refresh-hash"
    assert uow.saved[0].expires_at == now + timedelta(days=2)
    assert result.access_token == "access"
    assert result.refresh_token == "refresh"


def test_identity_core_dependency_boundaries():
    core = Path(__file__).resolve().parents[1] / "app" / "core"
    forbidden = (
        "fastapi",
        "sqlmodel",
        "sqlalchemy",
        "pydantic",
        "jwt",
        "pwdlib",
        "app.adapters",
        "app.bootstrap",
    )
    for component in ("users", "auth"):
        for path in (core / component).rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                imports = []
                if isinstance(node, ast.Import):
                    imports = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    assert node.level == 0, f"Use explicit imports in {path}"
                    imports = [node.module or ""]
                for name in imports:
                    assert not name.startswith(forbidden), (path, name)
                    if name.startswith("app.core."):
                        assert name.startswith(f"app.core.{component}.") or (
                            component == "auth" and name == "app.core.users.public"
                        ), (path, name)
                    if "domain" in path.parts:
                        assert ".application" not in name, (path, name)
