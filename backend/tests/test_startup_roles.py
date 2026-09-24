import importlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import app.model_registry  # noqa: F401 -- register FK targets
from app.adapters.outbound.persistence.users.models import Role, User
from app.core.users.domain.user import RoleName
from app.main import app

startup = importlib.import_module("app.bootstrap.lifespan")


@pytest.fixture
def database(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    monkeypatch.setattr(startup, "engine", engine)
    yield engine
    engine.dispose()


@pytest.mark.parametrize("existing", [False, True])
def test_startup_creates_only_missing_roles_and_preserves_ids(database, existing):
    SQLModel.metadata.create_all(database)
    if existing:
        with Session(database) as session:
            session.add(Role(id=42, name="ADMIN"))
            session.commit()
    snapshots = []
    for _ in range(2):
        with TestClient(app) as client:
            assert client.get("/").status_code == 200
            with Session(database) as session:
                snapshots.append({r.name: r.id for r in session.exec(select(Role))})
                assert session.exec(select(User)).all() == []
    assert set(snapshots[0]) == {role.value for role in RoleName}
    assert snapshots[0] == snapshots[1]
    if existing:
        assert snapshots[0]["ADMIN"] == 42


def test_missing_schema_aborts_startup(database):
    with pytest.raises(OperationalError):
        with TestClient(app):
            pytest.fail("Startup must fail without migrated tables")
