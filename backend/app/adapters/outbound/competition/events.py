from datetime import timezone

from app.adapters.outbound.persistence.competition.matches import TeamMatch
from app.adapters.outbound.persistence.competition.teams import Team
from app.core.content.events.public import SyncMatchEventCommand


class CompetitionMatchEvents:
    def __init__(self, session, sync_match):
        self.session, self.sync_match = session, sync_match

    def synchronize(self, match_id: int) -> bool:
        match = self.session.get(TeamMatch, match_id)
        if match is None:
            raise ValueError("Begegnung nicht gefunden.")
        team = self.session.get(Team, match.team_id)
        if team is None:
            raise ValueError("Mannschaft nicht gefunden.")

        def aware(value):
            return (
                value.replace(tzinfo=timezone.utc)
                if value is not None and value.tzinfo is None
                else value
            )

        _, created = self.sync_match.execute(
            SyncMatchEventCommand(
                match_id=match_id,
                team_name=team.name,
                opponent_name=match.opponent_name,
                is_home=match.is_home,
                scheduled_at=aware(match.scheduled_at),
                ended_at=aware(match.ended_at),
                status=match.status,
                is_completed=match.is_completed,
                venue_name=match.venue_name,
                venue_street=match.venue_street,
                venue_city=match.venue_city,
            )
        )
        return created
