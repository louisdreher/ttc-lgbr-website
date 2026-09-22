"""Transaction-aware Competition contracts for integration adapters."""

from sqlmodel import Session, select

from app.adapters.outbound.persistence.competition.seasons import Season
from app.adapters.outbound.persistence.competition.teams import Team, TeamAssignment


def assigned_player_period(session: Session, team_id: int, player_id: int) -> tuple[int, str] | None:
    """Return year/half of an internal assignment, locking its team until commit.

    Uses the same team lock as assignment writes/removal. No commits here.
    """
    team = session.exec(select(Team).where(Team.id == team_id).with_for_update()).first()
    if team is None or session.get(TeamAssignment, (team_id, player_id)) is None:
        return None
    season = session.get(Season, team.season_id)
    return season.start_year, season.half.value
