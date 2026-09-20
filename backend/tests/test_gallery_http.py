from datetime import date, datetime, timezone
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import app.model_registry  # noqa: F401
from app.adapters.inbound.http.auth.dependencies import get_current_user
from app.adapters.inbound.http.media.dependencies import provide_create_gallery
from app.adapters.inbound.http.media.router import router
from app.adapters.outbound.persistence.database import get_session
from app.adapters.outbound.persistence.events.models import Event, EventCategory
from app.adapters.outbound.persistence.media.models import Gallery
from app.adapters.outbound.persistence.users.models import User
from app.core.content.media.application.dto import CreatedGallery
from app.core.content.media.application.errors import (
    EventGalleryAlreadyExists, GalleryAccessDenied, ImageNotFound,
)
from app.core.content.media.domain.gallery import GalleryError
from app.core.users.public import UserDetails

URL = "/api/admin/media/galleries"


def authenticate(app, role="EDITOR"):
    app.dependency_overrides[get_current_user] = lambda: UserDetails(
        id=7, email="gallery@example.test", name="Writer", is_active=True, roles=[role],
    )


@pytest.fixture
def api():
    app = FastAPI()
    app.include_router(router)
    use_case = Mock()
    use_case.execute.return_value = CreatedGallery(10, 42, date(2007, 6, 16), True)
    app.dependency_overrides[provide_create_gallery] = lambda: use_case
    return app, use_case


@pytest.mark.parametrize("role", ["ADMIN", "EDITOR", "TEAM_REPORTER"])
def test_roles_identity_and_response(api, role):
    app, use_case = api
    authenticate(app, role)
    response = TestClient(app).post(URL, json={"title": " Turnier ", "event_id": 3, "media_ids": [42]})
    assert response.status_code == 201
    assert response.json() == dict(id=10, cover_image_id=42, gallery_date="2007-06-16", show_date=True)
    command = use_case.execute.call_args.args[0]
    assert command.title == "Turnier"
    assert command.user_id == 7 and command.can_upload
    assert command.can_manage_media is (role in {"ADMIN", "EDITOR"})
    assert command.event_id == 3 and command.media_ids == (42,)
    assert command.gallery_date is None and command.show_date is None


@pytest.mark.parametrize("role,status", [(None, 401), ("MEMBER", 403)])
def test_unauthorized(api, role, status):
    app, use_case = api
    if role:
        authenticate(app, role)
    assert TestClient(app).post(URL, json={"title": "Test"}).status_code == status
    use_case.execute.assert_not_called()


@pytest.mark.parametrize("values", [
    {"title": " "}, {"event_id": 0}, {"event_id": True}, {"media_ids": [-1]},
    {"media_ids": [True]}, {"gallery_date": "2007-02-30"}, {"show_date": "false"},
    {"user_id": 999}, {"can_upload": True}, {"can_manage_media": True},
])
def test_invalid_or_privileged_fields_are_rejected(api, values):
    app, use_case = api
    authenticate(app)
    assert TestClient(app).post(URL, json={"title": "Test"} | values).status_code == 422
    use_case.execute.assert_not_called()


def test_explicit_date_and_display_choice(api):
    app, use_case = api
    authenticate(app)
    TestClient(app).post(URL, json={"title": "Test", "gallery_date": "2007-06-16", "show_date": False})
    command = use_case.execute.call_args.args[0]
    assert command.gallery_date == date(2007, 6, 16)
    assert command.show_date is False and command.media_ids == ()


@pytest.mark.parametrize("error,status", [
    (GalleryAccessDenied("Nicht erlaubt"), 403),
    (EventGalleryAlreadyExists("Galerie existiert"), 409),
    (ImageNotFound(), 404), (GalleryError("Datum fehlt"), 422),
    (SQLAlchemyError("private database details"), 500),
])
def test_error_mapping(api, error, status):
    app, use_case = api
    authenticate(app)
    use_case.execute.side_effect = error
    response = TestClient(app).post(URL, json={"title": "Test"})
    assert response.status_code == status
    assert "private database details" not in response.text


def test_real_http_creation_defaults_conflict_and_validation():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(id=7, email="gallery@example.test", name="Editor", password_hash="test"))
        session.add(EventCategory(id=1, name="Turnier", slug="turnier"))
        session.flush()
        session.add(Event(id=3, title="Event", category_id=1,
                          starts_at=datetime(2007, 6, 15, 23, 30, tzinfo=timezone.utc)))
        session.commit()
    app = FastAPI()
    app.include_router(router)
    authenticate(app)

    def sessions():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = sessions
    try:
        with TestClient(app) as client:
            event = client.post(URL, json={"title": "Eventgalerie", "event_id": 3})
            assert event.status_code == 201
            assert event.json()["gallery_date"] == "2007-06-16"
            assert event.json()["show_date"] is True
            assert client.post(URL, json={"title": "Duplikat", "event_id": 3}).status_code == 409
            assert client.post(URL, json={"title": "Ohne Datum"}).status_code == 422
            assert client.post(URL, json={"title": "Bild fehlt", "gallery_date": "2007-06-16", "media_ids": [999]}).status_code == 404
            standalone = client.post(URL, json={"title": "Archiv", "gallery_date": "2007-06-16"})
            assert standalone.status_code == 201
            assert standalone.json()["show_date"] is False
            authenticate(app, "TEAM_REPORTER")
            assert client.post(URL, json={"title": "Archiv", "gallery_date": "2007-06-16"}).status_code == 403
        with Session(engine) as session:
            assert len(session.exec(select(Gallery)).all()) == 2
    finally:
        engine.dispose()
