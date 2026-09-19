from io import BytesIO
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import app.model_registry  # noqa: F401
from app.adapters.inbound.http.auth.dependencies import get_current_user
from app.adapters.inbound.http.media.router import router
from app.adapters.outbound.media.local_storage import LocalMediaStorage
from app.adapters.outbound.persistence.database import get_session
from app.adapters.outbound.persistence.media.models import MediaAsset
from app.adapters.outbound.persistence.users.models import User
from app.bootstrap.settings import settings
from app.core.content.media.application.dto import GetImageQuery, ImageReference
from app.core.content.media.application.errors import ImageNotFound, InvalidStorageKey
from app.core.content.media.application.queries import GetImage
from app.core.users.public import UserDetails


@pytest.mark.parametrize("reference", [None, ImageReference("images/private.webp", 2)])
def test_unavailable_image_does_not_read_storage(reference):
    reader, storage = Mock(), Mock()
    reader.get_image.return_value = reference
    with pytest.raises(ImageNotFound):
        GetImage(reader, storage).execute(GetImageQuery(42, 1))
    storage.read.assert_not_called()


def test_storage_rejects_traversal_and_reports_missing_file(tmp_path):
    storage = LocalMediaStorage(tmp_path)
    with pytest.raises(InvalidStorageKey):
        storage.read("../outside.webp")
    with pytest.raises(ImageNotFound):
        storage.read("images/" + "0" * 32 + ".webp")


@pytest.fixture
def uploaded(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(id=1, email="owner@example.test", name="Owner", password_hash="test"))
        session.commit()
    app = FastAPI()
    app.include_router(router)

    def sessions():
        with Session(engine) as session:
            yield session

    def identity(user_id, role):
        app.dependency_overrides[get_current_user] = lambda: UserDetails(
            id=user_id, email="user@example.test", name="User", is_active=True, roles=[role]
        )

    app.dependency_overrides[get_session] = sessions
    monkeypatch.setattr(settings, "media_directory", str(tmp_path))
    identity(1, "TEAM_REPORTER")
    with TestClient(app) as client:
        with Image.new("RGB", (80, 40), "red") as image, BytesIO() as output:
            image.save(output, format="PNG")
            response = client.post(
                "/api/admin/media/images", files={"file": ("team.png", output.getvalue())}
            )
        assert response.status_code == 201
        media_id = response.json()["id"]
        with Session(engine) as session:
            key = session.exec(select(MediaAsset)).one().storage_key
        yield client, app, identity, media_id, tmp_path / key, engine
    engine.dispose()


@pytest.mark.parametrize("user_id, role", [(1, "TEAM_REPORTER"), (1, "MEMBER"), (2, "EDITOR"), (2, "ADMIN")])
def test_owner_and_editors_can_retrieve_actual_image(uploaded, user_id, role):
    client, app, identity, media_id, path, engine = uploaded
    identity(user_id, role)
    response = client.get(f"/api/admin/media/images/{media_id}")
    assert response.status_code == 200
    assert response.content == path.read_bytes()
    assert response.headers["content-type"] == "image/webp"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    with Image.open(BytesIO(response.content)) as image:
        assert image.size == (80, 40)


@pytest.mark.parametrize("role", ["TEAM_REPORTER", "MEMBER"])
def test_foreign_upload_is_indistinguishable_from_missing(uploaded, role):
    client, app, identity, media_id, path, engine = uploaded
    identity(2, role)
    denied = client.get(f"/api/admin/media/images/{media_id}")
    missing = client.get("/api/admin/media/images/9999")
    assert denied.status_code == missing.status_code == 404
    assert denied.json() == missing.json()


def test_missing_file_and_anonymous_access(uploaded):
    client, app, identity, media_id, path, engine = uploaded
    path.unlink()
    assert client.get(f"/api/admin/media/images/{media_id}").status_code == 404
    app.dependency_overrides.pop(get_current_user)
    assert client.get(f"/api/admin/media/images/{media_id}").status_code == 401


def test_invalid_stored_key_does_not_expose_server_paths(uploaded):
    client, app, identity, media_id, path, engine = uploaded
    with Session(engine) as session:
        row = session.get(MediaAsset, media_id)
        row.storage_key = "../private.webp"
        session.add(row)
        session.commit()
    response = client.get(f"/api/admin/media/images/{media_id}")
    assert response.status_code == 500
    assert "private.webp" not in response.text
