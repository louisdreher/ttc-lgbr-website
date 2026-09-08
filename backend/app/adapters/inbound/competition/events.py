"""Bridge from the existing Competition import to the public Events contract.

Competition has not been migrated yet. Its ORM access is confined here;
the Events application receives only an immutable snapshot.
"""

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.bootstrap.events import build_sync_match_event
from app.core.competition.matches.models import TeamMatch
from app.core.competition.teams.model import Team
from app.core.content.events.public import SyncMatchEventCommand


class TeamMatchEventSync:
    def sync_one(self, session: Session, team_match: TeamMatch):
        if team_match.id is None:
            raise ValueError(
                "TeamMatch muss vor der Event-Synchronisierung gespeichert sein."
            )
        team = session.get(Team, team_match.team_id)
        if team is None:
            raise ValueError(f"Team {team_match.team_id} wurde nicht gefunden.")
        data = SyncMatchEventCommand(
            match_id=team_match.id,
            team_name=team.name,
            opponent_name=team_match.opponent_name,
            is_home=team_match.is_home,
            scheduled_at=_with_timezone(team_match.scheduled_at),
            ended_at=_with_timezone(team_match.ended_at),
            status=team_match.status,
            is_completed=team_match.is_completed,
            venue_name=team_match.venue_name,
            venue_street=team_match.venue_street,
            venue_city=team_match.venue_city,
        )
        return build_sync_match_event(session).execute(data)

    def backfill(
        self, session: Session, *, completed_only: bool = False
    ) -> tuple[int, int]:
        query = select(TeamMatch).order_by(TeamMatch.id)
        if completed_only:
            query = query.where(TeamMatch.is_completed.is_(True))
        created_count = updated_count = 0
        for match in session.exec(query).all():
            _, created = self.sync_one(session, match)
            if created:
                created_count += 1
            else:
                updated_count += 1
        return created_count, updated_count


def _with_timezone(value: datetime | None) -> datetime | None:
    # SQLite does not round-trip timezone metadata, unlike PostgreSQL.
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
