"""Supported cross-component contracts for imports, articles and galleries."""

from datetime import datetime
from typing import Protocol
from app.core.content.events.application.article_events import CreateHiddenArticleEvent
from app.core.content.events.application.dto import (
    CreateEventCommand,
    EventDetails,
    SyncMatchEventCommand,
)
from app.core.content.events.application.ports import EventReader
from app.core.content.events.application.sync_match import SyncMatchEvent


class GalleryEventReader(Protocol):
    def lock_for_gallery(self, event_id: int) -> datetime | None:
        """Lock the event until transaction end and return its start, or None."""
        ...


__all__ = [
    "GalleryEventReader",
    "EventDetails",
    "EventReader",
    "SyncMatchEvent",
    "SyncMatchEventCommand",
    "CreateHiddenArticleEvent",
    "CreateEventCommand",
]
