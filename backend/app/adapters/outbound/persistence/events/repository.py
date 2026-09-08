from dataclasses import asdict, fields
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.adapters.outbound.persistence.events.models import Event as EventRow
from app.adapters.outbound.persistence.events.models import EventCategory as CategoryRow
from app.core.content.events.domain.category import EventCategory
from app.core.content.events.domain.event import Event


def event_from_row(row: EventRow) -> Event:
    values = {item.name: getattr(row, item.name) for item in fields(Event)}
    # PostgreSQL preserves timezone information; SQLite test storage does not.
    for name, value in values.items():
        if isinstance(value, datetime) and value.tzinfo is None:
            values[name] = value.replace(tzinfo=timezone.utc)
    return Event(**values)


def category_from_row(row: CategoryRow) -> EventCategory:
    return EventCategory(
        **{item.name: getattr(row, item.name) for item in fields(EventCategory)}
    )


class SqlEventRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, event_id: int) -> Event | None:
        row = self.session.get(EventRow, event_id)
        return event_from_row(row) if row is not None else None

    def get_many(self, event_ids: list[int]) -> list[Event]:
        rows = self.session.exec(
            select(EventRow).where(EventRow.id.in_(set(event_ids)))
        ).all()
        return [event_from_row(row) for row in rows]

    def get_by_match(self, match_id: int) -> Event | None:
        row = self.session.exec(
            select(EventRow).where(EventRow.team_match_id == match_id)
        ).first()
        return event_from_row(row) if row is not None else None

    def save(self, event: Event) -> Event:
        row = self.session.get(EventRow, event.id) if event.id is not None else None
        if row is None:
            row = EventRow(**asdict(event))
        else:
            row.sqlmodel_update(asdict(event))
        self.session.add(row)
        self.session.flush()
        event.id = row.id
        return event

    def delete(self, event: Event) -> None:
        row = self.session.get(EventRow, event.id)
        if row is not None:
            self.session.delete(row)


class SqlCategoryRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, category_id: int) -> EventCategory | None:
        row = self.session.get(CategoryRow, category_id)
        return category_from_row(row) if row is not None else None

    def get_by_slug(self, slug: str) -> EventCategory | None:
        row = self.session.exec(
            select(CategoryRow).where(CategoryRow.slug == slug)
        ).first()
        return category_from_row(row) if row is not None else None

    def save(self, category: EventCategory) -> EventCategory:
        row = (
            self.session.get(CategoryRow, category.id)
            if category.id is not None
            else None
        )
        if row is None:
            row = CategoryRow(**asdict(category))
        else:
            row.sqlmodel_update(asdict(category))
        self.session.add(row)
        self.session.flush()
        category.id = row.id
        return category
