import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import app.model_registry  # noqa: F401 -- register foreign-key targets
from app.adapters.inbound.http.events.admin_router import event_manager
from app.adapters.inbound.http.events.admin_router import router as admin_router
from app.adapters.inbound.http.events.public_router import router as public_router
from app.adapters.outbound.persistence.database import get_session
from app.adapters.outbound.persistence.events.models import Event, EventCategory
from app.adapters.outbound.persistence.events.repository import SqlEventRepository
from app.adapters.outbound.persistence.events.unit_of_work import SqlEventUnitOfWork
from app.core.content.events.application.commands import UpdateEventsVisibility
from app.core.content.events.application.dto import UpdateEventsVisibilityCommand
from app.core.content.events.application.errors import EventNotFoundError
from app.core.content.types import Visibility
from app.core.users.model import User


class EventHttpTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        SQLModel.metadata.create_all(
            self.engine,
            tables=[Event.__table__, EventCategory.__table__, User.__table__],
        )
        with Session(self.engine) as session:
            session.add(
                User(
                    id=1,
                    email="editor@example.org",
                    name="Editor",
                    password_hash="test-only",
                )
            )
            session.add(EventCategory(id=1, name="Turnier", slug="turnier"))
            session.commit()
        self.app = FastAPI()
        self.app.include_router(admin_router)
        self.app.include_router(public_router)

        def session_override():
            with Session(self.engine) as session:
                yield session

        self.app.dependency_overrides[get_session] = session_override
        self.app.dependency_overrides[event_manager] = lambda: User(
            id=1, email="editor@example.org", name="Editor", password_hash="test-only"
        )
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.engine.dispose()

    def create(self, **changes):
        payload = {
            "title": "Turnier",
            "starts_at": "2026-09-01T18:00:00Z",
            "category_id": 1,
        }
        payload.update(changes)
        response = self.client.post("/api/admin/events", json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_create_read_update_delete_and_creator_projection(self):
        event = self.create(description="Hinweis", ends_at="2026-09-01T20:00:00Z")
        self.assertEqual(event["created_by_name"], "Editor")
        self.assertEqual(event["created_by_user_id"], 1)
        endpoint = f"/api/admin/events/{event['id']}"
        response = self.client.patch(endpoint, json={"title": " Neuer Titel "})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["description"], "Hinweis")
        self.assertEqual(response.json()["title"], "Neuer Titel")
        response = self.client.patch(
            endpoint, json={"ends_at": None, "description": None}
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNone(response.json()["ends_at"])
        self.assertIsNone(response.json()["description"])
        self.assertEqual(self.client.get(endpoint).status_code, 200)
        self.assertEqual(self.client.delete(endpoint).status_code, 204)
        self.assertEqual(self.client.get(endpoint).status_code, 404)

    def test_category_create_update_conflict_and_inactive_category(self):
        response = self.client.post(
            "/api/admin/event-categories", json={"name": "Ausflug", "slug": "ausflug"}
        )
        self.assertEqual(response.status_code, 201, response.text)
        category_id = response.json()["id"]
        endpoint = f"/api/admin/event-categories/{category_id}"
        self.assertEqual(
            self.client.patch(endpoint, json={"slug": "turnier"}).status_code, 409
        )
        self.assertEqual(
            self.client.post(
                "/api/admin/event-categories",
                json={"name": "Doppelt", "slug": "ausflug"},
            ).status_code,
            409,
        )
        self.assertEqual(
            self.client.patch(endpoint, json={"is_active": False}).status_code, 200
        )
        response = self.client.post(
            "/api/admin/events",
            json={
                "title": "Ausflug",
                "starts_at": "2026-09-01T18:00:00Z",
                "category_id": category_id,
            },
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            self.client.patch(
                "/api/admin/event-categories/999", json={"name": "Fehlt"}
            ).status_code,
            404,
        )

    def test_validation_remains_http_422(self):
        event = self.create()
        endpoint = f"/api/admin/events/{event['id']}"
        for payload in (
            {"is_all_day": None},
            {"title": None},
            {"title": " "},
            {"ends_at": "2026-08-01T18:00:00Z"},
            {"team_match_id": 7},
        ):
            with self.subTest(payload=payload):
                self.assertEqual(
                    self.client.patch(endpoint, json=payload).status_code, 422
                )

    def test_public_filter_and_response_fields(self):
        event = self.create()
        self.create(visibility="HIDDEN")
        with Session(self.engine) as session:
            session.add(
                Event(
                    title="Spiel",
                    starts_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
                    category_id=1,
                    team_match_id=7,
                )
            )
            session.commit()
        response = self.client.get(
            "/api/events",
            params={
                "starts_from": "2026-09-01T00:00:00Z",
                "starts_until": "2026-10-01T00:00:00Z",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual([item["id"] for item in response.json()], [event["id"]])
        self.assertNotIn("created_by_user_id", response.json()[0])
        self.assertNotIn("visibility", response.json()[0])
        self.assertEqual(self.client.get("/api/admin/event-years").json(), [2026])
        self.assertEqual(
            len(self.client.get("/api/admin/events", params={"year": 2026}).json()), 3
        )
        self.assertEqual(len(self.client.get("/api/event-categories").json()), 1)

    def test_bad_public_period_returns_422(self):
        for until in ("2026-08-01T00:00:00Z", "2026-10-01T00:00:00"):
            response = self.client.get(
                "/api/events",
                params={"starts_from": "2026-09-01T00:00:00Z", "starts_until": until},
            )
            self.assertEqual(response.status_code, 422, response.text)

    def test_bulk_visibility_and_delete(self):
        first, second = self.create(), self.create()
        ids = [first["id"], second["id"], first["id"]]
        response = self.client.patch(
            "/api/admin/events/bulk/visibility",
            json={"event_ids": ids, "visibility": "HIDDEN"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()), 2)
        self.assertTrue(
            all(
                item["visibility"] == "HIDDEN" and item["created_by_name"] == "Editor"
                for item in response.json()
            )
        )
        self.assertEqual(
            self.client.post(
                "/api/admin/events/bulk-delete", json={"event_ids": ids}
            ).status_code,
            204,
        )
        self.assertEqual(self.client.get("/api/admin/events").json(), [])

    def test_missing_bulk_id_does_not_change_existing_event(self):
        event = self.create()
        with Session(self.engine) as session:
            with self.assertRaises(EventNotFoundError):
                UpdateEventsVisibility(SqlEventUnitOfWork(session)).execute(
                    UpdateEventsVisibilityCommand(
                        event_ids=[event["id"], 999], visibility=Visibility.HIDDEN
                    )
                )
            self.assertEqual(
                session.get(Event, event["id"]).visibility, Visibility.PUBLIC
            )

    def test_late_repository_failure_rolls_back_already_flushed_writes(self):
        first, second = self.create(), self.create()
        original_save = SqlEventRepository.save
        count = 0

        def fail_second_save(repository, event):
            nonlocal count
            count += 1
            result = original_save(repository, event)
            if count == 2:
                raise RuntimeError("simulated write failure after flush")
            return result

        with (
            Session(self.engine) as session,
            patch.object(SqlEventRepository, "save", fail_second_save),
            self.assertRaises(RuntimeError),
        ):
            UpdateEventsVisibility(SqlEventUnitOfWork(session)).execute(
                UpdateEventsVisibilityCommand(
                    event_ids=[first["id"], second["id"]], visibility=Visibility.HIDDEN
                )
            )
        with Session(self.engine) as session:
            self.assertTrue(
                all(
                    row.visibility == Visibility.PUBLIC
                    for row in session.exec(select(Event)).all()
                )
            )
