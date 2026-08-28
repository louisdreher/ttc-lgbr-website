import unittest
from datetime import datetime, timedelta, timezone

from app.domains.competition.matches.models import TeamMatch
from app.domains.content.events.admin_router import event_manager
from app.domains.content.events.model import Event, EventCategory
from app.domains.content.events.schemas import (
    EventCategoryCreate,
    EventCreate,
    EventUpdate,
)
from app.domains.content.events.service import (
    EventCategoryInactiveError,
    EventServiceError,
    SyncedEventFieldError,
    create_event,
    create_event_category,
    update_event,
)
from app.domains.content.types import Visibility
from app.domains.users.model import Role, RoleName, User
from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine


class EventServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(
            self.engine,
            tables=[
                EventCategory.__table__,
                Event.__table__,
            ],
        )

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_create_event_uses_category_report_default(self) -> None:
        with Session(self.engine) as session:
            category = self._create_category(session, report_expected=True)

            event = create_event(
                session,
                EventCreate(
                    title=" Vereinsausflug ",
                    starts_at=self._starts_at(),
                    category_id=category.id,
                ),
            )

            self.assertEqual(event.title, "Vereinsausflug")
            self.assertTrue(event.report_expected)
            self.assertEqual(event.visibility, Visibility.PUBLIC)
            self.assertIsNone(event.team_match_id)

    def test_explicit_report_value_overrides_category_default(self) -> None:
        with Session(self.engine) as session:
            category = self._create_category(session, report_expected=True)

            event = create_event(
                session,
                EventCreate(
                    title="Meldeschluss",
                    starts_at=self._starts_at(),
                    category_id=category.id,
                    report_expected=False,
                ),
            )

            self.assertFalse(event.report_expected)

    def test_inactive_category_is_rejected(self) -> None:
        with Session(self.engine) as session:
            category = self._create_category(session, is_active=False)

            with self.assertRaises(EventCategoryInactiveError):
                create_event(
                    session,
                    EventCreate(
                        title="Nicht möglich",
                        starts_at=self._starts_at(),
                        category_id=category.id,
                    ),
                )

    def test_end_before_start_is_rejected(self) -> None:
        with Session(self.engine) as session:
            category = self._create_category(session)
            starts_at = self._starts_at()

            with self.assertRaises(EventServiceError):
                create_event(
                    session,
                    EventCreate(
                        title="Ungültiger Zeitraum",
                        starts_at=starts_at,
                        ends_at=starts_at - timedelta(hours=1),
                        category_id=category.id,
                    ),
                )

    def test_synced_event_only_accepts_editorial_updates(self) -> None:
        with Session(self.engine) as session:
            category = self._create_category(session)
            event = Event(
                title="TTC – Gast",
                starts_at=self._starts_at(),
                category_id=category.id,
                team_match_id=42,
            )
            session.add(event)
            session.commit()
            session.refresh(event)

            updated = update_event(
                session,
                event.id,
                EventUpdate(
                    description="Redaktioneller Hinweis",
                    report_expected=True,
                ),
            )
            self.assertEqual(updated.description, "Redaktioneller Hinweis")
            self.assertTrue(updated.report_expected)

            with self.assertRaises(SyncedEventFieldError):
                update_event(
                    session,
                    event.id,
                    EventUpdate(title="Manuell überschrieben"),
                )

    def test_admin_and_editor_are_allowed_to_manage_events(self) -> None:
        for role_name in (RoleName.ADMIN, RoleName.EDITOR):
            with self.subTest(role=role_name):
                user = self._user_with_role(role_name)
                self.assertIs(event_manager(user), user)

    def test_team_reporter_cannot_manage_events(self) -> None:
        with self.assertRaises(HTTPException) as context:
            event_manager(self._user_with_role(RoleName.TEAM_REPORTER))

        self.assertEqual(context.exception.status_code, 403)

    def _create_category(
        self,
        session: Session,
        *,
        report_expected: bool = False,
        is_active: bool = True,
    ) -> EventCategory:
        return create_event_category(
            session,
            EventCategoryCreate(
                name="Veranstaltung",
                slug="veranstaltung",
                default_report_expected=report_expected,
                is_active=is_active,
            ),
        )

    @staticmethod
    def _starts_at() -> datetime:
        return datetime(2026, 9, 1, 18, 30, tzinfo=timezone.utc)

    @staticmethod
    def _user_with_role(role_name: RoleName) -> User:
        return User(
            id=1,
            email="editor@example.org",
            name="Editor",
            password_hash="unused-in-test",
            roles=[Role(id=1, name=role_name.value)],
        )


if __name__ == "__main__":
    unittest.main()
