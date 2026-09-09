"""Compose Events use cases with SQL adapters; contains no FastAPI dependencies."""

from sqlmodel import Session

from app.adapters.outbound.persistence.events.reader import SqlEventReader
from app.adapters.outbound.persistence.events.repository import (
    SqlCategoryRepository,
    SqlEventRepository,
)
from app.adapters.outbound.persistence.events.unit_of_work import SqlEventUnitOfWork
from app.adapters.outbound.persistence.users.reader import SqlUserReader
from app.core.content.events.application import commands, queries
from app.core.content.events.public import SyncMatchEvent


def build_create_event_category(session: Session) -> commands.CreateEventCategory:
    return commands.CreateEventCategory(SqlEventUnitOfWork(session))


def build_update_event_category(session: Session) -> commands.UpdateEventCategory:
    return commands.UpdateEventCategory(SqlEventUnitOfWork(session))


def build_create_event(session: Session) -> commands.CreateEvent:
    return commands.CreateEvent(SqlEventUnitOfWork(session))


def build_update_event(session: Session) -> commands.UpdateEvent:
    return commands.UpdateEvent(SqlEventUnitOfWork(session))


def build_delete_event(session: Session) -> commands.DeleteEvent:
    return commands.DeleteEvent(SqlEventUnitOfWork(session))


def build_delete_events(session: Session) -> commands.DeleteEvents:
    return commands.DeleteEvents(SqlEventUnitOfWork(session))


def build_update_events_visibility(session: Session) -> commands.UpdateEventsVisibility:
    return commands.UpdateEventsVisibility(SqlEventUnitOfWork(session))


def build_list_event_categories(session: Session) -> queries.ListEventCategories:
    return queries.ListEventCategories(SqlEventReader(session, SqlUserReader(session)))


def build_list_public_event_categories(
    session: Session,
) -> queries.ListPublicEventCategories:
    return queries.ListPublicEventCategories(SqlEventReader(session, SqlUserReader(session)))


def build_list_event_years(session: Session) -> queries.ListEventYears:
    return queries.ListEventYears(SqlEventReader(session, SqlUserReader(session)))


def build_list_events(session: Session) -> queries.ListEvents:
    return queries.ListEvents(SqlEventReader(session, SqlUserReader(session)))


def build_get_event(session: Session) -> queries.GetEvent:
    return queries.GetEvent(SqlEventReader(session, SqlUserReader(session)))


def build_get_events(session: Session) -> queries.GetEvents:
    return queries.GetEvents(SqlEventReader(session, SqlUserReader(session)))


def build_list_public_events(session: Session) -> queries.ListPublicEvents:
    return queries.ListPublicEvents(SqlEventReader(session, SqlUserReader(session)))


def build_sync_match_event(session: Session) -> SyncMatchEvent:
    return SyncMatchEvent(SqlEventRepository(session), SqlCategoryRepository(session))
