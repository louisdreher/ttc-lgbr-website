"""Public SQL read projection for composition by other persistence adapters.

This infrastructure-only contract keeps event table details owned by Events.
It exposes event_id, title, starts_at, ends_at and team_match_id; callers may
join/filter the projection before counting and paginating. No rows are locked.
"""

from datetime import datetime

from sqlalchemy import func
from sqlmodel import select

from app.adapters.outbound.persistence.events.models import Event


def past_report_events(as_of: datetime):
    return select(
        Event.id.label("event_id"), Event.title, Event.starts_at,
        Event.ends_at, Event.team_match_id,
    ).where(
        Event.report_expected.is_(True),
        func.coalesce(Event.ends_at, Event.starts_at) < as_of,
    )
