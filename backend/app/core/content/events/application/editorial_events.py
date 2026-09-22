"""Transaction-participating contract for optional editorial events."""

from dataclasses import asdict

from app.core.content.events.application.dto import CreateEventCommand
from app.core.content.events.application.errors import EventCategoryNotFoundError
from app.core.content.events.application.ports import (
    CategoryRepository,
    EventRepository,
)
from app.core.content.events.domain.event import Event
from app.core.content.types import Visibility


class CreateHiddenEditorialEvent:
    def __init__(self, events: EventRepository, categories: CategoryRepository):
        self.events, self.categories = events, categories

    def execute(self, command: CreateEventCommand) -> int:
        category = self.categories.get(command.category_id)
        if category is None:
            raise EventCategoryNotFoundError("Event-Kategorie nicht gefunden.")
        category.ensure_active()
        values = asdict(command)
        values.update(visibility=Visibility.HIDDEN, report_expected=True)
        event = self.events.save(Event.create(**values))
        # Caller owns the transaction containing the event and its editorial content.
        return event.id
