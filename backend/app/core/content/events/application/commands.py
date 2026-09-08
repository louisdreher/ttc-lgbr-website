from dataclasses import asdict

from app.core.content.events.application.dto import (
    CreateEventCategoryCommand,
    CreateEventCommand,
    DeleteEventCommand,
    DeleteEventsCommand,
    UpdateEventCategoryCommand,
    UpdateEventCommand,
    UpdateEventsVisibilityCommand,
)
from app.core.content.events.application.errors import (
    EventCategoryNotFoundError,
    EventCategorySlugConflictError,
    EventNotFoundError,
)
from app.core.content.events.application.ports import EventUnitOfWork
from app.core.content.events.domain.category import EventCategory
from app.core.content.events.domain.event import Event, utc_now


def _event(uow: EventUnitOfWork, event_id: int) -> Event:
    event = uow.events.get(event_id)
    if event is None:
        raise EventNotFoundError("Event nicht gefunden.")
    return event


def _category(uow: EventUnitOfWork, category_id: int) -> EventCategory:
    category = uow.categories.get(category_id)
    if category is None:
        raise EventCategoryNotFoundError("Event-Kategorie nicht gefunden.")
    return category


def _ensure_slug_available(uow: EventUnitOfWork, category: EventCategory) -> None:
    existing = uow.categories.get_by_slug(category.slug)
    if existing is not None and existing.id != category.id:
        raise EventCategorySlugConflictError(
            "Eine Event-Kategorie mit diesem Slug existiert bereits."
        )


class CreateEventCategory:
    def __init__(self, uow: EventUnitOfWork):
        self.uow = uow

    def execute(self, command: CreateEventCategoryCommand) -> EventCategory:
        with self.uow:
            category = EventCategory.create(**asdict(command))
            _ensure_slug_available(self.uow, category)
            saved = self.uow.categories.save(category)
            self.uow.commit()
            return saved


class UpdateEventCategory:
    def __init__(self, uow: EventUnitOfWork):
        self.uow = uow

    def execute(self, command: UpdateEventCategoryCommand) -> EventCategory:
        with self.uow:
            category = _category(self.uow, command.category_id)
            category.edit(command.changes)
            _ensure_slug_available(self.uow, category)
            saved = self.uow.categories.save(category)
            self.uow.commit()
            return saved


class CreateEvent:
    def __init__(self, uow: EventUnitOfWork):
        self.uow = uow

    def execute(self, command: CreateEventCommand) -> Event:
        with self.uow:
            category = _category(self.uow, command.category_id)
            category.ensure_active()
            values = asdict(command)
            if command.report_expected is None:
                values["report_expected"] = category.default_report_expected
            event = Event.create(**values)
            saved = self.uow.events.save(event)
            self.uow.commit()
            return saved


class UpdateEvent:
    def __init__(self, uow: EventUnitOfWork):
        self.uow = uow

    def execute(self, command: UpdateEventCommand) -> Event:
        with self.uow:
            event = _event(self.uow, command.event_id)
            event.edit(command.changes)
            if "category_id" in command.changes:
                _category(self.uow, event.category_id).ensure_active()
            saved = self.uow.events.save(event)
            self.uow.commit()
            return saved


def _events(uow: EventUnitOfWork, event_ids: list[int]) -> list[Event]:
    events = uow.events.get_many(event_ids)
    if len(events) != len(set(event_ids)):
        raise EventNotFoundError(
            "Mindestens ein ausgewähltes Event wurde nicht gefunden."
        )
    return events


class DeleteEvent:
    def __init__(self, uow: EventUnitOfWork):
        self.uow = uow

    def execute(self, command: DeleteEventCommand) -> None:
        with self.uow:
            event = _event(self.uow, command.event_id)
            event.ensure_deletable()
            self.uow.events.delete(event)
            self.uow.commit()


class DeleteEvents:
    def __init__(self, uow: EventUnitOfWork):
        self.uow = uow

    def execute(self, command: DeleteEventsCommand) -> None:
        with self.uow:
            events = _events(self.uow, command.event_ids)
            for event in events:
                event.ensure_deletable()
            for event in events:
                self.uow.events.delete(event)
            self.uow.commit()


class UpdateEventsVisibility:
    def __init__(self, uow: EventUnitOfWork):
        self.uow = uow

    def execute(self, command: UpdateEventsVisibilityCommand) -> list[Event]:
        with self.uow:
            events = _events(self.uow, command.event_ids)
            now = utc_now()
            for event in events:
                event.change_visibility(command.visibility, now=now)
                self.uow.events.save(event)
            self.uow.commit()
            return events
