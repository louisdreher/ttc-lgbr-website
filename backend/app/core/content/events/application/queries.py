from app.core.content.events.application.dto import (
    EventDetails,
    GetEventQuery,
    GetEventsQuery,
    ListEventsQuery,
    ListPublicEventsQuery,
)
from app.core.content.events.application.errors import EventNotFoundError
from app.core.content.events.application.ports import EventReader
from app.core.content.events.domain.category import EventCategory
from app.core.content.events.domain.errors import EventServiceError


class ListEventCategories:
    def __init__(self, reader: EventReader):
        self.reader = reader

    def execute(self) -> list[EventCategory]:
        return self.reader.categories()


class ListPublicEventCategories:
    def __init__(self, reader: EventReader):
        self.reader = reader

    def execute(self) -> list[EventCategory]:
        return self.reader.categories(public=True)


class ListEventYears:
    def __init__(self, reader: EventReader):
        self.reader = reader

    def execute(self) -> list[int]:
        return self.reader.years()


class ListEvents:
    def __init__(self, reader: EventReader):
        self.reader = reader

    def execute(self, query: ListEventsQuery) -> list[EventDetails]:
        return self.reader.list(year=query.year, category_ids=query.category_ids)


class GetEvent:
    def __init__(self, reader: EventReader):
        self.reader = reader

    def execute(self, query: GetEventQuery) -> EventDetails:
        event = self.reader.get(query.event_id)
        if event is None:
            raise EventNotFoundError("Event nicht gefunden.")
        return event


class GetEvents:
    def __init__(self, reader: EventReader):
        self.reader = reader

    def execute(self, query: GetEventsQuery) -> list[EventDetails]:
        events = self.reader.get_many(query.event_ids)
        if len(events) != len(set(query.event_ids)):
            raise EventNotFoundError(
                "Mindestens ein ausgewähltes Event wurde nicht gefunden."
            )
        return events


class ListPublicEvents:
    def __init__(self, reader: EventReader):
        self.reader = reader

    def execute(self, query: ListPublicEventsQuery) -> list[EventDetails]:
        if (query.starts_from.utcoffset() is None) != (
            query.starts_until.utcoffset() is None
        ):
            raise EventServiceError(
                "Die Datumsgrenzen müssen dieselbe Zeitzonenangabe verwenden."
            )
        if query.starts_until < query.starts_from:
            raise EventServiceError(
                "Das Enddatum darf nicht vor dem Startdatum liegen."
            )
        return self.reader.public_list(
            starts_from=query.starts_from,
            starts_until=query.starts_until,
            category_ids=query.category_ids,
        )
