from datetime import datetime, timezone

from app.domains.competition.matches.models import TeamMatch
from app.domains.competition.teams.model import Team
from app.domains.content.events.model import Event, EventCategory, EventStatus
from app.domains.content.events.schemas import (
    EventCategoryCreate,
    EventCategoryUpdate,
    EventCreate,
    EventRead,
    EventUpdate,
)
from app.domains.content.types import Visibility
from app.domains.users.model import User
from sqlalchemy import extract
from sqlmodel import Session, select

TEAM_MATCH_CATEGORY_SLUG = "mannschaftsspiel"
TEAM_MATCH_CATEGORY_NAME = "Mannschaftsspiel"

SYNCED_EVENT_FIELDS = {
    "title",
    "starts_at",
    "ends_at",
    "is_all_day",
    "category_id",
    "status",
    "location",
}


class EventServiceError(ValueError):
    """Base class for expected event-domain validation errors."""


class EventNotFoundError(EventServiceError):
    pass


class EventCategoryNotFoundError(EventServiceError):
    pass


class EventCategoryInactiveError(EventServiceError):
    pass


class EventCategorySlugConflictError(EventServiceError):
    pass


class SyncedEventFieldError(EventServiceError):
    pass


class SyncedEventDeleteError(EventServiceError):
    pass


def list_event_categories(session: Session) -> list[EventCategory]:
    return list(
        session.exec(
            select(EventCategory).order_by(
                EventCategory.sort_order,
                EventCategory.name,
            )
        ).all()
    )


def list_public_event_categories(session: Session) -> list[EventCategory]:
    return list(
        session.exec(
            select(EventCategory)
            .where(
                EventCategory.is_active.is_(True),
                EventCategory.slug != TEAM_MATCH_CATEGORY_SLUG,
            )
            .order_by(EventCategory.sort_order, EventCategory.name)
        ).all()
    )


def create_event_category(
    session: Session,
    category_data: EventCategoryCreate,
) -> EventCategory:
    slug = category_data.slug.strip().lower()
    _ensure_category_slug_available(session, slug)

    category = EventCategory(
        **category_data.model_dump(exclude={"name", "slug"}),
        name=_required_text(category_data.name, "Der Kategoriename"),
        slug=slug,
    )
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


def update_event_category(
    session: Session,
    category_id: int,
    category_data: EventCategoryUpdate,
) -> EventCategory:
    category = session.get(EventCategory, category_id)
    if category is None:
        raise EventCategoryNotFoundError("Event-Kategorie nicht gefunden.")

    changes = category_data.model_dump(exclude_unset=True)
    _reject_nulls(
        changes,
        {
            "name",
            "slug",
            "default_report_expected",
            "is_active",
            "sort_order",
        },
    )

    if "name" in changes:
        changes["name"] = _required_text(changes["name"], "Der Kategoriename")

    if "slug" in changes:
        slug = changes["slug"].strip().lower()
        _ensure_category_slug_available(session, slug, exclude_id=category.id)
        changes["slug"] = slug

    category.sqlmodel_update(changes)
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


def list_event_years(session: Session) -> list[int]:
    years = session.exec(
        select(extract("year", Event.starts_at))
        .distinct()
        .order_by(extract("year", Event.starts_at).desc())
    ).all()
    return [int(year) for year in years]


def list_events(
    session: Session,
    *,
    year: int | None = None,
    category_ids: list[int] | None = None,
) -> list[Event]:
    statement = select(Event)
    if year is not None:
        statement = statement.where(extract("year", Event.starts_at) == year)
    if category_ids is not None:
        if not category_ids:
            return []
        statement = statement.where(Event.category_id.in_(category_ids))
    return list(session.exec(statement.order_by(Event.starts_at.desc())).all())


def list_public_events(
    session: Session,
    *,
    starts_from: datetime,
    starts_until: datetime,
    category_ids: list[int] | None = None,
) -> list[Event]:
    statement = select(Event).where(
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
        statement = statement.where(Event.category_id.in_(category_ids))
    return list(session.exec(statement.order_by(Event.starts_at, Event.id)).all())


def serialize_events(session: Session, events: list[Event]) -> list[EventRead]:
    user_ids = {
        event.created_by_user_id
        for event in events
        if event.created_by_user_id is not None
    }
    users = (
        session.exec(select(User).where(User.id.in_(user_ids))).all()
        if user_ids
        else []
    )
    names = {user.id: user.name for user in users}
    return [
        EventRead.model_validate(
            event,
            update={"created_by_name": names.get(event.created_by_user_id)},
        )
        for event in events
    ]


def get_event(session: Session, event_id: int) -> Event:
    event = session.get(Event, event_id)
    if event is None:
        raise EventNotFoundError("Event nicht gefunden.")
    return event


def create_event(
    session: Session, event_data: EventCreate, *, created_by_user_id: int | None = None
) -> Event:
    category = _get_active_category(session, event_data.category_id)
    _validate_period(event_data.starts_at, event_data.ends_at)

    data = event_data.model_dump(exclude={"title", "report_expected"})
    event = Event(
        **data,
        title=_required_text(event_data.title, "Der Event-Titel"),
        report_expected=(
            category.default_report_expected
            if event_data.report_expected is None
            else event_data.report_expected
        ),
        created_by_user_id=created_by_user_id,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def delete_event(session: Session, event_id: int) -> None:
    event = get_event(session, event_id)
    _ensure_deletable([event])
    session.delete(event)
    session.commit()


def delete_events(session: Session, event_ids: list[int]) -> None:
    events = _get_events_by_ids(session, event_ids)
    _ensure_deletable(events)
    for event in events:
        session.delete(event)
    session.commit()


def update_events_visibility(
    session: Session, event_ids: list[int], visibility: Visibility
) -> list[Event]:
    events = _get_events_by_ids(session, event_ids)
    now = datetime.now(timezone.utc)
    for event in events:
        event.visibility = visibility
        event.updated_at = now
        session.add(event)
    session.commit()
    for event in events:
        session.refresh(event)
    return events


def _get_events_by_ids(session: Session, event_ids: list[int]) -> list[Event]:
    unique_ids = set(event_ids)
    events = list(session.exec(select(Event).where(Event.id.in_(unique_ids))).all())
    if len(events) != len(unique_ids):
        raise EventNotFoundError(
            "Mindestens ein ausgewähltes Event wurde nicht gefunden."
        )
    return events


def _ensure_deletable(events: list[Event]) -> None:
    if any(event.team_match_id is not None for event in events):
        raise SyncedEventDeleteError(
            "Synchronisierte Mannschaftsspiele können nicht gelöscht werden."
        )


def update_event(
    session: Session,
    event_id: int,
    event_data: EventUpdate,
) -> Event:
    event = get_event(session, event_id)
    changes = event_data.model_dump(exclude_unset=True)
    _reject_nulls(
        changes,
        {
            "title",
            "starts_at",
            "category_id",
            "status",
            "visibility",
            "report_expected",
        },
    )

    if event.team_match_id is not None:
        protected_changes = SYNCED_EVENT_FIELDS.intersection(changes)
        if protected_changes:
            fields = ", ".join(sorted(protected_changes))
            raise SyncedEventFieldError(
                f"Synchronisierte Event-Felder können nicht geändert werden: {fields}."
            )

    if "category_id" in changes:
        _get_active_category(session, changes["category_id"])

    if "title" in changes:
        changes["title"] = _required_text(changes["title"], "Der Event-Titel")

    starts_at = changes.get("starts_at", event.starts_at)
    ends_at = changes.get("ends_at", event.ends_at)
    if "starts_at" in changes or "ends_at" in changes:
        _validate_period(starts_at, ends_at)

    event.sqlmodel_update(changes)
    event.updated_at = datetime.now(timezone.utc)
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def _get_active_category(session: Session, category_id: int) -> EventCategory:
    category = session.get(EventCategory, category_id)
    if category is None:
        raise EventCategoryNotFoundError("Event-Kategorie nicht gefunden.")
    if not category.is_active:
        raise EventCategoryInactiveError(
            "Deaktivierte Event-Kategorien können nicht verwendet werden."
        )
    return category


def _ensure_category_slug_available(
    session: Session,
    slug: str,
    *,
    exclude_id: int | None = None,
) -> None:
    statement = select(EventCategory).where(EventCategory.slug == slug)
    existing = session.exec(statement).first()
    if existing is not None and existing.id != exclude_id:
        raise EventCategorySlugConflictError(
            "Eine Event-Kategorie mit diesem Slug existiert bereits."
        )


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise EventServiceError(f"{field_name} darf nicht leer sein.")
    return normalized


def _validate_period(starts_at: datetime, ends_at: datetime | None) -> None:
    if starts_at.utcoffset() is None:
        raise EventServiceError("Der Beginn muss eine Zeitzone enthalten.")
    if ends_at is not None and ends_at.utcoffset() is None:
        raise EventServiceError("Das Ende muss eine Zeitzone enthalten.")
    if ends_at is not None and ends_at < starts_at:
        raise EventServiceError(
            "Das Ende eines Events darf nicht vor seinem Beginn liegen."
        )


def _reject_nulls(changes: dict, required_fields: set[str]) -> None:
    null_fields = sorted(
        field
        for field in required_fields
        if field in changes and changes[field] is None
    )
    if null_fields:
        fields = ", ".join(null_fields)
        raise EventServiceError(f"Diese Felder dürfen nicht null sein: {fields}.")


class TeamMatchEventSync:
    def sync_one(
        self,
        session: Session,
        team_match: TeamMatch,
    ) -> tuple[Event, bool]:
        """Erzeugt oder aktualisiert das Event eines Mannschaftsspiels.

        Der Rückgabewert enthält das Event und ``True``, wenn es neu angelegt
        wurde. Redaktionelle Felder eines bestehenden Events bleiben erhalten.
        """

        if team_match.id is None:
            raise ValueError(
                "TeamMatch muss vor der Event-Synchronisierung gespeichert sein."
            )

        team = session.get(Team, team_match.team_id)

        if team is None:
            raise ValueError(f"Team {team_match.team_id} wurde nicht gefunden.")

        category = self._get_or_create_category(session)
        category_id = category.id

        if category_id is None:
            raise RuntimeError("EventCategory wurde nicht gespeichert.")

        event = session.exec(
            select(Event).where(Event.team_match_id == team_match.id)
        ).first()
        created = event is None

        if event is None:
            event = Event(
                title=self._build_title(team_match, team),
                starts_at=team_match.scheduled_at,
                ends_at=self._get_ends_at(team_match),
                is_all_day=False,
                category_id=category_id,
                team_match_id=team_match.id,
                status=self._get_status(team_match),
                report_expected=category.default_report_expected,
                location=self._build_location(team_match),
            )
            session.add(event)
        else:
            # Diese Felder gehören zum extern synchronisierten Spielplan.
            # Beschreibung, Sichtbarkeit und Berichtserwartung sind dagegen
            # redaktionell und werden bei Updates bewusst nicht überschrieben.
            event.title = self._build_title(team_match, team)
            event.starts_at = team_match.scheduled_at
            event.ends_at = self._get_ends_at(team_match)
            event.is_all_day = False
            event.category_id = category_id
            event.status = self._get_status(team_match)
            event.location = self._build_location(team_match)
            event.updated_at = datetime.now(timezone.utc)

        session.flush()

        return event, created

    def backfill(
        self,
        session: Session,
        *,
        completed_only: bool = False,
    ) -> tuple[int, int]:
        """Synchronisiert Events für bereits vorhandene Mannschaftsspiele.

        Gibt die Anzahl neu angelegter und aktualisierter Events zurück. Das
        Commit bleibt dem Aufrufer überlassen.
        """

        statement = select(TeamMatch).order_by(TeamMatch.id)

        if completed_only:
            statement = statement.where(TeamMatch.is_completed.is_(True))

        created_count = 0
        updated_count = 0

        for team_match in session.exec(statement).all():
            _, created = self.sync_one(session, team_match)

            if created:
                created_count += 1
            else:
                updated_count += 1

        return created_count, updated_count

    @staticmethod
    def _get_or_create_category(session: Session) -> EventCategory:
        category = session.exec(
            select(EventCategory).where(EventCategory.slug == TEAM_MATCH_CATEGORY_SLUG)
        ).first()

        if category is not None:
            return category

        category = EventCategory(
            name=TEAM_MATCH_CATEGORY_NAME,
            slug=TEAM_MATCH_CATEGORY_SLUG,
            default_report_expected=True,
        )
        session.add(category)
        session.flush()

        return category

    @staticmethod
    def _build_title(team_match: TeamMatch, team: Team) -> str:
        if team_match.is_home:
            return f"{team.name} – {team_match.opponent_name}"

        return f"{team_match.opponent_name} – {team.name}"

    @staticmethod
    def _build_location(team_match: TeamMatch) -> str | None:
        parts = [
            team_match.venue_name,
            team_match.venue_street,
            team_match.venue_city,
        ]
        location = ", ".join(part.strip() for part in parts if part and part.strip())

        return location or None

    @staticmethod
    def _get_ends_at(team_match: TeamMatch) -> datetime | None:
        """Ignoriert unvollständige historische Endzeiten ohne Spieldatum."""

        if team_match.ended_at is None or team_match.ended_at < team_match.scheduled_at:
            return None

        return team_match.ended_at

    @staticmethod
    def _get_status(team_match: TeamMatch) -> EventStatus:
        status = (team_match.status or "").casefold()

        if any(value in status for value in ("cancel", "abgesagt", "annull")):
            return EventStatus.CANCELLED

        if any(value in status for value in ("postpon", "verlegt", "verschoben")):
            return EventStatus.POSTPONED

        if team_match.is_completed:
            return EventStatus.COMPLETED

        return EventStatus.PLANNED
