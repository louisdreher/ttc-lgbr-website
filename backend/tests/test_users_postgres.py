"""Users migrations and concurrency checks in disposable PostgreSQL databases."""
# ruff: noqa: F811 -- imported pytest fixture is injected by parameter name.

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from alembic import command
from app.adapters.outbound.persistence.users.models import Role, User
from app.bootstrap.users import (
    build_ensure_default_roles,
    build_remove_user_role,
    build_set_password,
)
from app.core.users.application.dto import ChangeUserRoleCommand
from app.core.users.application.errors import (
    InvalidPasswordLinkError,
    UserConflictError,
)
from app.core.users.domain.user import RoleName
from sqlalchemy import inspect, text
from sqlmodel import Session, select
from test_outbox_postgres import postgres_database  # noqa: F401


@pytest.mark.parametrize("upgrade_existing", [False, True])
def test_users_migration(postgres_database, upgrade_existing):
    engine, config = postgres_database
    if upgrade_existing:
        command.upgrade(config, "c9e15f30a624")
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO \"user\" (email, name, password_hash, is_active, created_at) VALUES ('existing@example.org', 'Existing', '!', true, now())"
                )
            )
    command.upgrade(config, "head")
    command.check(config)
    assert "password_link" in inspect(engine).get_table_names()
    if upgrade_existing:
        with Session(engine) as session:
            user = session.exec(
                select(User).where(User.email == "existing@example.org")
            ).one()
            assert user.auth_invalid_before is None


def test_concurrent_last_admin_removal(postgres_database):
    engine, config = postgres_database
    command.upgrade(config, "head")
    with Session(engine) as session:
        build_ensure_default_roles(session).execute()
        role = session.exec(select(Role).where(Role.name == "ADMIN")).one()
        users = [
            User(
                name=f"Admin {n}",
                email=f"admin{n}@example.org",
                password_hash="!",
                roles=[role],
            )
            for n in range(2)
        ]
        session.add_all(users)
        session.commit()
        ids = [u.id for u in users]
    barrier = Barrier(2)

    def remove(uid):
        with Session(engine) as session:
            barrier.wait(timeout=10)
            try:
                build_remove_user_role(session).execute(
                    ChangeUserRoleCommand(user_id=uid, role_name=RoleName.ADMIN)
                )
                return True
            except UserConflictError:
                return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(remove, ids)) == [False, True]


def test_concurrent_password_link_consumption(postgres_database):
    from datetime import datetime, timedelta, timezone

    from app.adapters.outbound.persistence.users.models import PasswordLink
    from app.adapters.outbound.security.password_links import SecurePasswordLinkTokens

    engine, config = postgres_database
    command.upgrade(config, "head")
    with Session(engine) as session:
        build_ensure_default_roles(session).execute()
        user = User(name="Test", email="test@example.org", password_hash="!")
        session.add(user)
        session.flush()
        session.add(
            PasswordLink(
                user_id=user.id,
                token_hash=SecurePasswordLinkTokens().digest("test-token"),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            )
        )
        session.commit()
    barrier = Barrier(2)

    def consume(_):
        with Session(engine) as session:
            barrier.wait(timeout=10)
            try:
                build_set_password(session).execute("test-token", "test-password-long")
                return True
            except InvalidPasswordLinkError:
                return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(consume, range(2))) == [False, True]
