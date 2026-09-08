"""Domain and application tests deliberately need neither HTTP nor a database."""

import ast
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.content.events.application.commands import CreateEvent
from app.core.content.events.application.dto import CreateEventCommand
from app.core.content.events.domain.category import EventCategory
from app.core.content.events.domain.errors import (
    EventServiceError,
    SyncedEventFieldError,
)
from app.core.content.events.domain.event import Event

START = datetime(2026, 9, 1, 18, tzinfo=timezone.utc)


class EventDomainTest(unittest.TestCase):
    def test_period_rejects_naive_datetimes_and_reversed_order(self):
        for starts_at, ends_at in (
            (START.replace(tzinfo=None), None),
            (START, START.replace(tzinfo=None)),
            (START, START - timedelta(minutes=1)),
        ):
            with (
                self.subTest(starts_at=starts_at, ends_at=ends_at),
                self.assertRaises(EventServiceError),
            ):
                Event.create(
                    title="Termin",
                    starts_at=starts_at,
                    ends_at=ends_at,
                    category_id=1,
                )

    def test_partial_edit_distinguishes_omitted_and_cleared_values(self):
        event = Event.create(
            title="Termin",
            starts_at=START,
            ends_at=START + timedelta(hours=1),
            category_id=1,
            description="Hinweis",
        )
        event.edit({"title": " Neuer Titel "})
        self.assertEqual(event.description, "Hinweis")
        self.assertIsNotNone(event.ends_at)
        event.edit({"description": None, "ends_at": None})
        self.assertIsNone(event.description)
        self.assertIsNone(event.ends_at)
        self.assertEqual(event.title, "Neuer Titel")

    def test_invalid_edit_does_not_partially_change_entity(self):
        event = Event.create(title="Termin", starts_at=START, category_id=1)
        before = deepcopy(event)
        with self.assertRaises(EventServiceError):
            event.edit(
                {"title": "Anderer Titel", "ends_at": START - timedelta(hours=1)}
            )
        self.assertEqual(event, before)

    def test_null_all_day_is_rejected_as_a_domain_error(self):
        event = Event.create(title="Termin", starts_at=START, category_id=1)
        with self.assertRaises(EventServiceError):
            event.edit({"is_all_day": None})

    def test_editor_cannot_change_match_owned_fields_even_to_same_value(self):
        event = Event.create(
            title="Spiel", starts_at=START, category_id=1, team_match_id=7
        )
        with self.assertRaises(SyncedEventFieldError):
            event.edit({"starts_at": START})
        event.edit({"description": "Redaktioneller Hinweis"})
        self.assertEqual(event.description, "Redaktioneller Hinweis")

    def test_create_use_case_runs_with_in_memory_ports(self):
        class Categories:
            def get(self, category_id):
                return EventCategory(
                    id=category_id,
                    name="Turnier",
                    slug="turnier",
                    default_report_expected=True,
                )

        class Events:
            def save(self, event):
                event.id = 42
                return event

        class MemoryUnitOfWork:
            categories = Categories()
            events = Events()
            committed = False

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def commit(self):
                self.committed = True

        uow = MemoryUnitOfWork()
        result = CreateEvent(uow).execute(
            CreateEventCommand(
                title=" Turnier ", starts_at=START, category_id=1, created_by_user_id=3
            )
        )
        self.assertTrue(uow.committed)
        self.assertEqual(result.id, 42)
        self.assertEqual(result.title, "Turnier")
        self.assertEqual(result.created_by_user_id, 3)
        self.assertTrue(result.report_expected)

    def test_core_imports_only_stdlib_and_its_own_domain_contracts(self):
        root = Path(__file__).resolve().parents[1] / "app/core/content/events"
        for package in ("domain", "application"):
            for path in (root / package).glob("*.py"):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    imports = (
                        [node.module or ""]
                        if isinstance(node, ast.ImportFrom)
                        else [alias.name for alias in node.names]
                        if isinstance(node, ast.Import)
                        else []
                    )
                    for name in imports:
                        with self.subTest(file=path.name, imported=name):
                            self.assertFalse(
                                name.startswith(
                                    (
                                        "fastapi",
                                        "pydantic",
                                        "sqlmodel",
                                        "sqlalchemy",
                                        "app.adapters",
                                    )
                                )
                            )
                            if name.startswith("app."):
                                self.assertTrue(
                                    name.startswith("app.core.content.events.")
                                    or name == "app.core.content.types"
                                )
                            if package == "domain":
                                self.assertFalse(
                                    name.startswith(
                                        "app.core.content.events.application"
                                    )
                                )
