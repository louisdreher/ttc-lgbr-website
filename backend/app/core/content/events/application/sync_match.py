from app.core.content.events.application.dto import SyncMatchEventCommand
from app.core.content.events.application.ports import (
    CategoryRepository,
    EventRepository,
)
from app.core.content.events.domain.category import (
    TEAM_MATCH_CATEGORY_NAME,
    TEAM_MATCH_CATEGORY_SLUG,
    EventCategory,
)
from app.core.content.events.domain.event import Event, EventStatus


class SyncMatchEvent:
    def __init__(self, events: EventRepository, categories: CategoryRepository):
        self.events = events
        self.categories = categories

    def execute(self, command: SyncMatchEventCommand) -> tuple[Event, bool]:
        """Participates in the caller's transaction; never commits on its own."""
        category = self.categories.get_by_slug(TEAM_MATCH_CATEGORY_SLUG)
        if category is None:
            category = self.categories.save(
                EventCategory.create(
                    name=TEAM_MATCH_CATEGORY_NAME,
                    slug=TEAM_MATCH_CATEGORY_SLUG,
                    default_report_expected=True,
                )
            )
        if category.id is None:
            raise RuntimeError("EventCategory wurde nicht gespeichert.")
        status = (command.status or "").casefold()
        if any(value in status for value in ("cancel", "abgesagt", "annull")):
            event_status = EventStatus.CANCELLED
        elif any(value in status for value in ("postpon", "verlegt", "verschoben")):
            event_status = EventStatus.POSTPONED
        elif command.is_completed:
            event_status = EventStatus.COMPLETED
        else:
            event_status = EventStatus.PLANNED
        title = (
            f"{command.team_name} – {command.opponent_name}"
            if command.is_home
            else f"{command.opponent_name} – {command.team_name}"
        )
        location = (
            ", ".join(
                part.strip()
                for part in (
                    command.venue_name,
                    command.venue_street,
                    command.venue_city,
                )
                if part and part.strip()
            )
            or None
        )
        # Historical imports can contain an end time with a placeholder date.
        ends_at = command.ended_at
        if ends_at is not None and ends_at < command.scheduled_at:
            ends_at = None
        values = {
            "title": title,
            "starts_at": command.scheduled_at,
            "ends_at": ends_at,
            "category_id": category.id,
            "status": event_status,
            "location": location,
        }
        event = self.events.get_by_match(command.match_id)
        created = event is None
        if event is None:
            event = Event.create(
                **values,
                team_match_id=command.match_id,
                report_expected=category.default_report_expected,
            )
        else:
            event.synchronize(**values)
        return self.events.save(event), created
