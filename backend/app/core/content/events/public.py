"""Supported cross-component contract for match imports."""

from app.core.content.events.application.article_events import CreateHiddenArticleEvent
from app.core.content.events.application.dto import (
    CreateEventCommand,
    EventDetails,
    SyncMatchEventCommand,
)
from app.core.content.events.application.ports import EventReader
from app.core.content.events.application.sync_match import SyncMatchEvent

__all__ = [
    "EventDetails",
    "EventReader",
    "SyncMatchEvent",
    "SyncMatchEventCommand",
    "CreateHiddenArticleEvent",
    "CreateEventCommand",
]
