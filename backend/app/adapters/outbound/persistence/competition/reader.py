from datetime import datetime

from sqlmodel import select

from app.adapters.outbound.persistence.competition.leagues import (
    LeagueGroup,
    LeagueTableEntry,
)
from app.adapters.outbound.persistence.competition.matches import TeamMatch
from app.adapters.outbound.persistence.competition.seasons import Season
from app.adapters.outbound.persistence.competition.seasons import (
    SeasonHalf as StoredSeasonHalf,
)
from app.adapters.outbound.persistence.competition.teams import Team
from app.core.competition.application.imports import GroupReference, MeetingReference
from app.core.competition.domain.seasons import SeasonHalf, SeasonKey


class SqlCompetitionReader:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def meeting(self, match_id: int) -> MeetingReference:
        with self.session_factory() as session:
            row = session.get(TeamMatch, match_id)
            if row is None:
                raise ValueError(f"TeamMatch {match_id} existiert nicht.")
            if row.mytt_meeting_id is None:
                raise ValueError(f"TeamMatch {match_id} hat keine myTT meeting_id.")
            return MeetingReference(
                id=row.id,
                external_id=row.mytt_meeting_id,
                imported=row.details_imported_at is not None,
            )

    def match_id(self, external_id: int) -> int:
        with self.session_factory() as session:
            value = session.exec(
                select(TeamMatch.id).where(TeamMatch.mytt_meeting_id == external_id)
            ).first()
            if value is None:
                raise ValueError(
                    f"Kein TeamMatch mit myTT meeting_id {external_id} gefunden."
                )
            return value

    def group(self, group_id: int, *, require_team: bool = False) -> GroupReference:
        with self.session_factory() as session:
            group = session.get(LeagueGroup, group_id)
            if group is None:
                raise ValueError(f"LeagueGroup {group_id} existiert nicht.")
            season = session.get(Season, group.season_id)
            if season is None:
                raise RuntimeError("Season existiert nicht.")
            team = None
            if require_team:
                team = session.exec(
                    select(Team)
                    .where(Team.league_group_id == group_id)
                    .order_by(Team.id)
                ).first()
                if team is None or team.mytt_team_id is None or group.mytt_slug is None:
                    raise ValueError(
                        "Ligagruppe benötigt ein eigenes Team mit externer ID und einen Slug."
                    )
            return GroupReference(
                id=group.id,
                season=SeasonKey(
                    season.start_year, season.end_year, SeasonHalf(season.half.value)
                ),
                external_id=group.mytt_group_id,
                external_slug=group.mytt_slug,
                team_external_id=team.mytt_team_id if team else None,
                team_name=team.name if team else None,
            )

    def season_id(self, season: SeasonKey) -> int | None:
        with self.session_factory() as session:
            return session.exec(
                select(Season.id).where(
                    Season.start_year == season.start_year,
                    Season.end_year == season.end_year,
                    Season.half == StoredSeasonHalf(season.half.value),
                )
            ).first()

    def group_ids(
        self, season_id: int | None = None, *, with_team: bool = False
    ) -> list[int]:
        with self.session_factory() as session:
            query = select(LeagueGroup.id)
            if season_id is not None:
                query = query.where(LeagueGroup.season_id == season_id)
            if with_team:
                query = query.join(
                    Team, Team.league_group_id == LeagueGroup.id
                ).distinct()
            return list(session.exec(query.order_by(LeagueGroup.id)).all())

    def pending_match_ids(
        self, *, season_id: int | None = None, before: datetime | None = None
    ) -> list[int]:
        with self.session_factory() as session:
            query = select(TeamMatch.id).where(TeamMatch.details_imported_at.is_(None))
            if season_id is not None:
                query = query.join(Team, Team.id == TeamMatch.team_id).where(
                    Team.season_id == season_id, TeamMatch.is_completed.is_(True)
                )
            else:
                query = query.where(TeamMatch.mytt_meeting_id.is_not(None))
            if before is not None:
                query = query.where(TeamMatch.scheduled_at < before)
            return list(
                session.exec(query.order_by(TeamMatch.scheduled_at, TeamMatch.id)).all()
            )

    def has_standings(self, group_id: int) -> bool:
        with self.session_factory() as session:
            return (
                session.exec(
                    select(LeagueTableEntry.id)
                    .where(LeagueTableEntry.league_group_id == group_id)
                    .limit(1)
                ).first()
                is not None
            )
