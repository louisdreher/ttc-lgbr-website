"""Adapt request-scoped FastAPI sessions to the Events composition factories."""

from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from app.adapters.outbound.persistence.database import get_session
from app.bootstrap import events as wiring
from app.core.content.events.application import commands, queries


def provide_create_event_category(
    session: Annotated[Session, Depends(get_session)],
) -> commands.CreateEventCategory:
    return wiring.build_create_event_category(session)


def provide_update_event_category(
    session: Annotated[Session, Depends(get_session)],
) -> commands.UpdateEventCategory:
    return wiring.build_update_event_category(session)


def provide_create_event(
    session: Annotated[Session, Depends(get_session)],
) -> commands.CreateEvent:
    return wiring.build_create_event(session)


def provide_update_event(
    session: Annotated[Session, Depends(get_session)],
) -> commands.UpdateEvent:
    return wiring.build_update_event(session)


def provide_delete_event(
    session: Annotated[Session, Depends(get_session)],
) -> commands.DeleteEvent:
    return wiring.build_delete_event(session)


def provide_delete_events(
    session: Annotated[Session, Depends(get_session)],
) -> commands.DeleteEvents:
    return wiring.build_delete_events(session)


def provide_update_events_visibility(
    session: Annotated[Session, Depends(get_session)],
) -> commands.UpdateEventsVisibility:
    return wiring.build_update_events_visibility(session)


def provide_list_event_categories(
    session: Annotated[Session, Depends(get_session)],
) -> queries.ListEventCategories:
    return wiring.build_list_event_categories(session)


def provide_list_public_event_categories(
    session: Annotated[Session, Depends(get_session)],
) -> queries.ListPublicEventCategories:
    return wiring.build_list_public_event_categories(session)


def provide_list_event_years(
    session: Annotated[Session, Depends(get_session)],
) -> queries.ListEventYears:
    return wiring.build_list_event_years(session)


def provide_list_events(
    session: Annotated[Session, Depends(get_session)],
) -> queries.ListEvents:
    return wiring.build_list_events(session)


def provide_get_event(
    session: Annotated[Session, Depends(get_session)],
) -> queries.GetEvent:
    return wiring.build_get_event(session)


def provide_get_events(
    session: Annotated[Session, Depends(get_session)],
) -> queries.GetEvents:
    return wiring.build_get_events(session)


def provide_list_public_events(
    session: Annotated[Session, Depends(get_session)],
) -> queries.ListPublicEvents:
    return wiring.build_list_public_events(session)
