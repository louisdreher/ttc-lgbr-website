import unittest
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.adapters.inbound.http.events.admin_router import event_manager
from app.adapters.outbound.persistence.events.models import Event, EventCategory
from app.adapters.outbound.persistence.events.reader import SqlEventReader
from app.adapters.outbound.persistence.events.unit_of_work import SqlEventUnitOfWork
from app.core.competition.matches.models import (
    TeamMatch,  # noqa: F401 -- register FK target
)
from app.core.content.events.application import commands, queries
from app.core.content.events.application.dto import (
    CreateEventCategoryCommand,
    CreateEventCommand,
    DeleteEventCommand,
    DeleteEventsCommand,
    ListEventsQuery,
    ListPublicEventsQuery,
    UpdateEventCommand,
    UpdateEventsVisibilityCommand,
)
from app.core.content.events.domain.errors import (
    EventCategoryInactiveError,
    EventServiceError,
    SyncedEventDeleteError,
    SyncedEventFieldError,
)
from app.core.content.types import Visibility
from app.core.users.model import Role, RoleName, User


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

            event = commands.CreateEvent(SqlEventUnitOfWork(session)).execute(
                CreateEventCommand(
                    title=" Vereinsausflug ",
                    starts_at=self._starts_at(),
                    category_id=category.id,
                )
            )

            self.assertEqual(event.title, "Vereinsausflug")
            self.assertTrue(event.report_expected)
            self.assertEqual(event.visibility, Visibility.PUBLIC)
            self.assertIsNone(event.team_match_id)

    def test_explicit_report_value_overrides_category_default(self) -> None:
        with Session(self.engine) as session:
            category = self._create_category(session, report_expected=True)

            event = commands.CreateEvent(SqlEventUnitOfWork(session)).execute(
                CreateEventCommand(
                    title="Meldeschluss",
                    starts_at=self._starts_at(),
                    category_id=category.id,
                    report_expected=False,
                )
            )

            self.assertFalse(event.report_expected)

    def test_inactive_category_is_rejected(self) -> None:
        with Session(self.engine) as session:
            category = self._create_category(session, is_active=False)

            with self.assertRaises(EventCategoryInactiveError):
                commands.CreateEvent(SqlEventUnitOfWork(session)).execute(
                    CreateEventCommand(
                        title="Nicht möglich",
                        starts_at=self._starts_at(),
                        category_id=category.id,
                    )
                )

    def test_end_before_start_is_rejected(self) -> None:
        with Session(self.engine) as session:
            category = self._create_category(session)
            starts_at = self._starts_at()

            with self.assertRaises(EventServiceError):
                commands.CreateEvent(SqlEventUnitOfWork(session)).execute(
                    CreateEventCommand(
                        title="Ungültiger Zeitraum",
                        starts_at=starts_at,
                        ends_at=starts_at - timedelta(hours=1),
                        category_id=category.id,
                    )
                )

    def test_events_can_be_filtered_by_year_and_category(self) -> None:
        with Session(self.engine) as session:
            first = self._create_category(session)
            second = commands.CreateEventCategory(SqlEventUnitOfWork(session)).execute(
                CreateEventCategoryCommand(name="Turnier", slug="turnier")
            )
            commands.CreateEvent(SqlEventUnitOfWork(session)).execute(
                CreateEventCommand(
                    title="Alt",
                    starts_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                    category_id=first.id,
                )
            )
            commands.CreateEvent(SqlEventUnitOfWork(session)).execute(
                CreateEventCommand(
                    title="Neu",
                    starts_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    category_id=second.id,
                )
            )

            self.assertEqual(
                queries.ListEventYears(SqlEventReader(session)).execute(), [2026, 2025]
            )
            self.assertEqual(
                [
                    event.title
                    for event in queries.ListEvents(SqlEventReader(session)).execute(
                        ListEventsQuery(year=2026)
                    )
                ],
                ["Neu"],
            )
            self.assertEqual(
                queries.ListEvents(SqlEventReader(session)).execute(
                    ListEventsQuery(year=2026, category_ids=[first.id])
                ),
                [],
            )

    def test_public_events_only_include_public_manual_events_in_range(self) -> None:
        with Session(self.engine) as session:
            category = self._create_category(session)
            team_match_category = commands.CreateEventCategory(
                SqlEventUnitOfWork(session)
            ).execute(
                CreateEventCategoryCommand(
                    name="Mannschaftsspiel", slug="mannschaftsspiel"
                )
            )
            visible = commands.CreateEvent(SqlEventUnitOfWork(session)).execute(
                CreateEventCommand(
                    title="Öffentlich",
                    starts_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
                    category_id=category.id,
                )
            )
            commands.CreateEvent(SqlEventUnitOfWork(session)).execute(
                CreateEventCommand(
                    title="Verborgen",
                    starts_at=datetime(2026, 9, 3, tzinfo=timezone.utc),
                    category_id=category.id,
                    visibility=Visibility.HIDDEN,
                )
            )
            session.add(
                Event(
                    title="Mannschaftsspiel",
                    starts_at=datetime(2026, 9, 4, tzinfo=timezone.utc),
                    category_id=category.id,
                    team_match_id=42,
                )
            )
            commands.CreateEvent(SqlEventUnitOfWork(session)).execute(
                CreateEventCommand(
                    title="Manuelles Mannschaftsspiel",
                    starts_at=datetime(2026, 9, 5, tzinfo=timezone.utc),
                    category_id=team_match_category.id,
                )
            )
            session.commit()

            events = queries.ListPublicEvents(SqlEventReader(session)).execute(
                ListPublicEventsQuery(
                    starts_from=datetime(2026, 9, 1, tzinfo=timezone.utc),
                    starts_until=datetime(2026, 9, 30, tzinfo=timezone.utc),
                )
            )

            self.assertEqual([event.id for event in events], [visible.id])

    def test_public_categories_exclude_inactive_and_team_matches(self) -> None:
        with Session(self.engine) as session:
            visible = self._create_category(session)
            commands.CreateEventCategory(SqlEventUnitOfWork(session)).execute(
                CreateEventCategoryCommand(
                    name="Mannschaftsspiel", slug="mannschaftsspiel"
                )
            )
            commands.CreateEventCategory(SqlEventUnitOfWork(session)).execute(
                CreateEventCategoryCommand(
                    name="Inaktiv", slug="inaktiv", is_active=False
                )
            )

            self.assertEqual(
                queries.ListPublicEventCategories(SqlEventReader(session)).execute(),
                [visible],
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

            updated = commands.UpdateEvent(SqlEventUnitOfWork(session)).execute(
                UpdateEventCommand(
                    changes={
                        "description": "Redaktioneller Hinweis",
                        "report_expected": True,
                    },
                    event_id=event.id,
                )
            )
            self.assertEqual(updated.description, "Redaktioneller Hinweis")
            self.assertTrue(updated.report_expected)

            with self.assertRaises(SyncedEventFieldError):
                commands.UpdateEvent(SqlEventUnitOfWork(session)).execute(
                    UpdateEventCommand(
                        changes={"title": "Manuell überschrieben"}, event_id=event.id
                    )
                )

    def test_delete_event_rejects_synced_events(self) -> None:
        with Session(self.engine) as session:
            category = self._create_category(session)
            manual = commands.CreateEvent(SqlEventUnitOfWork(session)).execute(
                CreateEventCommand(
                    title="Manuell",
                    starts_at=self._starts_at(),
                    category_id=category.id,
                )
            )
            synced = Event(
                title="Spiel",
                starts_at=self._starts_at(),
                category_id=category.id,
                team_match_id=42,
            )
            session.add(synced)
            session.commit()
            session.refresh(synced)

            with self.assertRaises(SyncedEventDeleteError):
                commands.DeleteEvents(SqlEventUnitOfWork(session)).execute(
                    DeleteEventsCommand(event_ids=[manual.id, synced.id])
                )
            self.assertIsNotNone(session.get(Event, manual.id))

            commands.DeleteEvent(SqlEventUnitOfWork(session)).execute(
                DeleteEventCommand(event_id=manual.id)
            )
            self.assertIsNone(session.get(Event, manual.id))

    def test_bulk_visibility_updates_synced_and_manual_events(self) -> None:
        with Session(self.engine) as session:
            category = self._create_category(session)
            first = commands.CreateEvent(SqlEventUnitOfWork(session)).execute(
                CreateEventCommand(
                    title="Eins", starts_at=self._starts_at(), category_id=category.id
                )
            )
            second = commands.CreateEvent(SqlEventUnitOfWork(session)).execute(
                CreateEventCommand(
                    title="Zwei", starts_at=self._starts_at(), category_id=category.id
                )
            )
            updated = commands.UpdateEventsVisibility(
                SqlEventUnitOfWork(session)
            ).execute(
                UpdateEventsVisibilityCommand(
                    event_ids=[first.id, second.id], visibility=Visibility.HIDDEN
                )
            )
            self.assertTrue(
                all(event.visibility == Visibility.HIDDEN for event in updated)
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
        return commands.CreateEventCategory(SqlEventUnitOfWork(session)).execute(
            CreateEventCategoryCommand(
                name="Veranstaltung",
                slug="veranstaltung",
                default_report_expected=report_expected,
                is_active=is_active,
            )
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
