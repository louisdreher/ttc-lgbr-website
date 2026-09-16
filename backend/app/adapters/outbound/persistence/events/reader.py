from __future__ import annotations

from datetime import datetime

from app.adapters.outbound.persistence.events.models import Event, EventCategory
from app.adapters.outbound.persistence.events.repository import category_from_row
from app.core.content.events.application.dto import EventDetails
from app.core.content.events.domain.category import TEAM_MATCH_CATEGORY_SLUG
from app.core.content.types import Visibility
from app.core.users.public import UserReader
from sqlalchemy import extract
from sqlmodel import Session, select


class SqlEventReader:
    def __init__(self, session: Session, users: UserReader):
        self.session = session
        self.users = users

    def categories(self, *, public: bool = False):
        query = select(EventCategory)
        if public:
            query = query.where(
                EventCategory.is_active.is_(True),
                EventCategory.slug != TEAM_MATCH_CATEGORY_SLUG,
            )
        rows = self.session.exec(
            query.order_by(EventCategory.sort_order, EventCategory.name)
        ).all()
        return [category_from_row(row) for row in rows]

    def years(self) -> list[int]:
        year = extract("year", Event.starts_at)
        return [
            int(value)
            for value in self.session.exec(
                select(year).distinct().order_by(year.desc())
            ).all()
        ]

    def _details(self, rows: list[Event]) -> list[EventDetails]:
        # A read-side projection: no User or ORM model escapes this adapter.
        user_ids = {
            row.created_by_user_id for row in rows if row.created_by_user_id is not None
        }
        names = self.users.get_names(user_ids)
        return [
            EventDetails(
                **row.model_dump(), created_by_name=names.get(row.created_by_user_id)
            )
            for row in rows
        ]

    def get(self, event_id: int) -> EventDetails | None:
        row = self.session.get(Event, event_id)
        return self._details([row])[0] if row is not None else None

    def get_by_match(self, team_match_id: int) -> EventDetails | None:
        row = self.session.exec(
            select(Event).where(Event.team_match_id == team_match_id)
        ).first()
        return self._details([row])[0] if row is not None else None

    def get_many(self, event_ids: list[int]) -> list[EventDetails]:
        rows = self.session.exec(select(Event).where(Event.id.in_(event_ids))).all()
        details = {item.id: item for item in self._details(list(rows))}
        return [
            details[event_id]
            for event_id in dict.fromkeys(event_ids)
            if event_id in details
        ]

    def list(
        self, *, year: int | None = None, category_ids: list[int] | None = None
    ) -> list[EventDetails]:
        query = select(Event)
        if year is not None:
            query = query.where(extract("year", Event.starts_at) == year)
        if category_ids is not None:
            if not category_ids:
                return []
            query = query.where(Event.category_id.in_(category_ids))
        return self._details(
            list(self.session.exec(query.order_by(Event.starts_at.desc())).all())
        )

    def public_list(
        self,
        *,
        starts_from: datetime,
        starts_until: datetime,
        category_ids: list[int] | None = None,
    ) -> list[EventDetails]:
        query = select(Event).where(
            Event.visibility == Visibility.PUBLIC,
            Event.team_match_id.is_(None),
            Event.category_id.not_in(
                select(EventCategory.id).where(
                    EventCategory.slug == TEAM_MATCH_CATEGORY_SLUG
                )
            ),
            Event.starts_at >= starts_from,
            Event.starts_at <= starts_until,
        )
        if category_ids:
            query = query.where(Event.category_id.in_(category_ids))
        rows = self.session.exec(query.order_by(Event.starts_at, Event.id)).all()
        return [EventDetails(**row.model_dump()) for row in rows]
