from io import BytesIO
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

import app.model_registry  # noqa: F401
from app.adapters.inbound.http.auth.dependencies import get_current_user
from app.adapters.inbound.http.media.dependencies import provide_upload_image
from app.adapters.inbound.http.media.router import router
from app.adapters.outbound.persistence.database import get_session
from app.adapters.outbound.persistence.media.models import MediaAsset
from app.adapters.outbound.persistence.users.models import User
from app.bootstrap.media import configured_media_directory
from app.bootstrap.settings import settings
from app.core.content.media.application.dto import UploadedImage
from app.core.content.media.application.errors import InvalidImage, MediaStorageError
from app.core.users.public import UserDetails

URL = "/api/admin/media/images"


@pytest.fixture
def api():
    app = FastAPI()
    app.include_router(router)
    use_case = Mock()
    use_case.execute.return_value = UploadedImage(42, "image/webp", 100, 80, 40)
    app.dependency_overrides[provide_upload_image] = lambda: use_case
    yield app, use_case


def authenticate(app, role="EDITOR"):
    app.dependency_overrides[get_current_user] = lambda: UserDetails(
        id=7, email="media@example.test", name="Editor", is_active=True, roles=[role]
    )


@pytest.mark.parametrize("role", ["ADMIN", "EDITOR", "TEAM_REPORTER"])
def test_upload_roles_and_authenticated_identity(api, role):
    app, use_case = api
    authenticate(app, role)
    response = TestClient(app).post(URL, files={"file": ("test.jpg", b"image", "image/jpeg")})
    assert response.status_code == 201
    assert response.json() == dict(id=42, mime_type="image/webp", file_size=100, width=80, height=40)
    command = use_case.execute.call_args.args[0]
    assert command.uploaded_by_user_id == 7
    assert command.original_filename == "test.jpg"
    assert command.data == b"image"


def test_anonymous_upload_is_rejected(api):
    app, use_case = api
    response = TestClient(app).post(URL, files={"file": ("a.jpg", b"image")})
    assert response.status_code == 401
    use_case.execute.assert_not_called()


def test_member_upload_is_rejected(api):
    app, use_case = api
    authenticate(app, "MEMBER")
    assert TestClient(app).post(URL, files={"file": ("a.jpg", b"image")}).status_code == 403
    use_case.execute.assert_not_called()


@pytest.mark.parametrize("data", [b"12345", b"x" * 70000], ids=["file-limit", "body-limit"])
def test_file_and_stream_limits(api, monkeypatch, data):
    app, use_case = api
    authenticate(app)
    monkeypatch.setattr(settings, "media_max_upload_bytes", 4)
    assert TestClient(app).post(URL, files={"file": ("a.jpg", data)}).status_code == 413
    use_case.execute.assert_not_called()


def test_stream_limit_without_content_length(api, monkeypatch):
    app, use_case = api
    authenticate(app)
    monkeypatch.setattr(settings, "media_max_upload_bytes", 4)
    def body():
        yield b'--test\r\nContent-Disposition: form-data; name="file"; filename="a.jpg"\r\n\r\n'
        yield b"x" * 70000
        yield b"\r\n--test--\r\n"
    response = TestClient(app).post(URL, content=body(), headers={"Content-Type": "multipart/form-data; boundary=test"})
    assert response.status_code == 413
    use_case.execute.assert_not_called()


@pytest.mark.parametrize("files", [
    {"wrong": ("a.jpg", b"image")},
    [("file", ("a.jpg", b"image")), ("file", ("b.jpg", b"image"))],
])
def test_wrong_field_or_multiple_files_are_rejected(api, files):
    app, use_case = api
    authenticate(app)
    assert TestClient(app).post(URL, files=files).status_code == 400
    use_case.execute.assert_not_called()


def test_client_cannot_supply_uploader(api):
    app, use_case = api
    authenticate(app)
    response = TestClient(app).post(URL, files={"file": ("a.jpg", b"image")}, data={"uploaded_by_user_id": "999"})
    assert response.status_code == 400
    use_case.execute.assert_not_called()


@pytest.mark.parametrize("error, status", [(InvalidImage("bad"), 422), (MediaStorageError("private path"), 500)])
def test_errors_are_translated_without_internal_details(api, error, status):
    app, use_case = api
    authenticate(app)
    use_case.execute.side_effect = error
    response = TestClient(app).post(URL, files={"file": ("a.jpg", b"image")})
    assert response.status_code == status
    assert "private path" not in response.text


def test_wrong_content_type_and_missing_boundary(api):
    app, use_case = api
    authenticate(app)
    client = TestClient(app)
    assert client.post(URL, json={}).status_code == 415
    assert client.post(URL, content=b"bad", headers={"Content-Type": "multipart/form-data"}).status_code == 400
    use_case.execute.assert_not_called()


def test_real_http_upload_persists_image_and_metadata(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(id=7, email="media@example.test", name="Editor", password_hash="test"))
        session.commit()
    app = FastAPI()
    app.include_router(router)
    authenticate(app)
    def sessions():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[get_session] = sessions
    monkeypatch.setattr(settings, "media_directory", str(tmp_path))
    try:
        with Image.new("RGB", (80, 40), "red") as image, BytesIO() as output:
            image.save(output, format="PNG")
            response = TestClient(app).post(URL, files={"file": ("team.png", output.getvalue())})
        assert response.status_code == 201, response.text
        with Session(engine) as session:
            row = session.exec(select(MediaAsset)).one()
            assert row.id == response.json()["id"]
            assert row.uploaded_by_user_id == 7
            assert (tmp_path / row.storage_key).stat().st_size == response.json()["file_size"]
    finally:
        engine.dispose()


def test_relative_media_directory_is_independent_of_cwd(tmp_path, monkeypatch):
    expected = configured_media_directory("output/media")
    monkeypatch.chdir(tmp_path)
    assert configured_media_directory("output/media") == expected
    assert configured_media_directory(str(tmp_path)) == tmp_path
