from datetime import datetime, timezone

from app.domains.competition.matches.models import TeamMatch
from app.domains.competition.teams.model import Team
from app.domains.content.events.model import Event, EventCategory, EventStatus
from sqlmodel import Session, select

TEAM_MATCH_CATEGORY_SLUG = "mannschaftsspiel"
TEAM_MATCH_CATEGORY_NAME = "Mannschaftsspiel"


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

        if (
            team_match.ended_at is None
            or team_match.ended_at < team_match.scheduled_at
        ):
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
