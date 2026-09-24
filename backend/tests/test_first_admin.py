from unittest.mock import Mock

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

import app.model_registry  # noqa: F401
from app.adapters.inbound.cli import users as cli
from app.adapters.outbound.persistence.users.models import User
from app.bootstrap.users import build_create_first_admin, build_ensure_default_roles
from app.core.users.application.dto import CreateUserCommand
from app.adapters.outbound.security.passwords import ArgonPasswords


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        build_ensure_default_roles(session).execute()
        yield session
    engine.dispose()


def command(email="first@example.org"):
    return CreateUserCommand(name=" First Admin ", email=email, password="test-password-123")


def test_create_admin_hashes_password_and_cannot_run_again(session):
    result = build_create_first_admin(session).execute(command())
    user = session.get(User, result.id)
    assert user.name == "First Admin" and user.is_active
    assert [r.name for r in user.roles] == ["ADMIN"]
    assert ArgonPasswords().verify("test-password-123", user.password_hash)
    for active in (True, False):
        user.is_active = active
        session.commit()
        with pytest.raises(ValueError, match="bereits ein Administrator"):
            build_create_first_admin(session).execute(command("second@example.org"))
    assert len(session.exec(select(User)).all()) == 1


def test_existing_account_is_not_promoted(session):
    user = User(name="Existing", email="first@example.org", password_hash="!")
    session.add(user)
    session.commit()
    with pytest.raises(ValueError, match="Konto"):
        build_create_first_admin(session).execute(command(" FIRST@EXAMPLE.ORG "))
    session.refresh(user)
    assert user.password_hash == "!" and user.roles == []


def test_failed_commit_rolls_back_account_and_role_link(session, monkeypatch):
    usecase = build_create_first_admin(session)
    monkeypatch.setattr(usecase.uow, "commit", Mock(side_effect=RuntimeError("failure")))
    with pytest.raises(RuntimeError):
        usecase.execute(command())
    assert session.exec(select(User)).all() == []


@pytest.mark.parametrize("password", ["short", "x" * 129])
def test_password_length_rejected(session, password):
    with pytest.raises(ValueError, match="12 bis 128"):
        build_create_first_admin(session).execute(
            CreateUserCommand(name="Admin", email="a@example.org", password=password)
        )
    assert session.exec(select(User)).all() == []


@pytest.mark.parametrize("scenario", ["success", "mismatch", "invalid_email", "no_terminal"])
def test_cli_interaction(session, monkeypatch, capsys, scenario):
    answers = iter(["Admin", "invalid" if scenario == "invalid_email" else "first@example.org"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    passwords = iter(["test-password-123", "different" if scenario == "mismatch" else "test-password-123"])

    def get_password(_):
        if scenario == "no_terminal":
            raise cli.getpass.GetPassWarning("no terminal")
        return next(passwords)

    monkeypatch.setattr(cli.getpass, "getpass", get_password)
    monkeypatch.setattr(cli, "engine", session.get_bind())
    assert cli.main(["create-admin"]) == (0 if scenario == "success" else 1)
    output = capsys.readouterr()
    assert "test-password-123" not in output.out + output.err
    assert len(session.exec(select(User)).all()) == (1 if scenario == "success" else 0)
