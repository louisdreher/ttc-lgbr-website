from collections.abc import Callable
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlmodel import Session, select

from app.adapters.outbound.persistence.competition.leagues import (
    LeagueGroup,
    LeagueTableEntry,
)
from app.adapters.outbound.persistence.competition.matches import (
    Match,
    MatchLineup,
    MatchParticipant,
    SetResult,
    TeamMatch,
    TeamMatchNotice,
)
from app.adapters.outbound.persistence.competition.seasons import Season
from app.adapters.outbound.persistence.competition.seasons import (
    SeasonHalf as StoredSeasonHalf,
)
from app.adapters.outbound.persistence.competition.teams import Team, TeamAssignment
from app.core.competition.application.dto import (
    GetMatchDetailsQuery,
    GetScheduleQuery,
    GetTeamLineupQuery,
    GetTeamStandingsQuery,
    ListTeamsQuery,
    MatchDetails,
    MatchGame,
    MatchLineupEntry,
    MatchNotice,
    MatchSet,
    ScheduledMatchSummary,
    StandingSummary,
    TeamLineup,
    TeamLineupEntry,
    TeamSummary,
)
from app.core.competition.application.ports import MatchPlayerReader
from app.core.competition.application.sync.imports import (
    GroupReference,
    MeetingReference,
)
from app.core.competition.domain.seasons import SeasonHalf, SeasonKey


class SqlCompetitionReader:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        players: MatchPlayerReader | None = None,
    ):
        self.session_factory = session_factory
        self.players = players

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

    def list_teams(self, query: ListTeamsQuery) -> list[TeamSummary]:
        statement = select(Team.id, Team.name, Team.team_number, Team.category).where(
            Team.season_id == query.season_id
        )

        if query.category is not None:
            statement = statement.where(Team.category == query.category)

        statement = statement.order_by(Team.category, Team.team_number, Team.id)

        with self.session_factory() as session:
            rows = session.exec(statement).all()

            return [
                TeamSummary(
                    id=row.id,
                    name=row.name,
                    team_number=row.team_number,
                    category=row.category,
                )
                for row in rows
            ]

    def get_schedule(self, query: GetScheduleQuery) -> list[ScheduledMatchSummary]:
        statement = (
            select(
                TeamMatch.id,
                TeamMatch.team_id,
                Team.name.label("team_name"),
                TeamMatch.opponent_name,
                TeamMatch.is_home,
                TeamMatch.scheduled_at,
                TeamMatch.status,
                TeamMatch.is_completed,
                TeamMatch.score_ttc,
                TeamMatch.score_opponent,
            )
            .join(Team, Team.id == TeamMatch.team_id)
            .where(
                TeamMatch.scheduled_at
                >= datetime.combine(
                    query.date_from, time.min, ZoneInfo("Europe/Berlin")
                ).astimezone(timezone.utc)
            )
            .order_by(TeamMatch.scheduled_at, TeamMatch.id)
        )
        if query.date_to < date.max:
            end = datetime.combine(
                query.date_to + timedelta(days=1), time.min, ZoneInfo("Europe/Berlin")
            ).astimezone(timezone.utc)
            statement = statement.where(TeamMatch.scheduled_at < end)
        if query.team_ids:
            statement = statement.where(TeamMatch.team_id.in_(query.team_ids))
        if query.category is not None:
            statement = statement.where(Team.category == query.category)
        with self.session_factory() as session:
            return [
                ScheduledMatchSummary(**row._mapping)
                for row in session.exec(statement).all()
            ]

    def get_team_standings(self, query: GetTeamStandingsQuery) -> list[StandingSummary]:
        statement = (
            select(
                LeagueTableEntry.team_name,
                LeagueTableEntry.position,
                (LeagueTableEntry.mytt_team_id == Team.mytt_team_id).label(
                    "is_selected_team"
                ),
                LeagueTableEntry.meetings_count,
                LeagueTableEntry.meetings_won,
                LeagueTableEntry.meetings_tie,
                LeagueTableEntry.meetings_lost,
                LeagueTableEntry.points_won,
                LeagueTableEntry.points_lost,
                LeagueTableEntry.matches_won,
                LeagueTableEntry.matches_lost,
                LeagueTableEntry.sets_won,
                LeagueTableEntry.sets_lost,
                LeagueTableEntry.games_won,
                LeagueTableEntry.games_lost,
            )
            .join(Team, Team.league_group_id == LeagueTableEntry.league_group_id)
            .where(Team.id == query.team_id)
            .order_by(LeagueTableEntry.position, LeagueTableEntry.id)
        )
        with self.session_factory() as session:
            return [
                StandingSummary(**row._mapping) for row in session.exec(statement).all()
            ]

    def get_match_details(self, query: GetMatchDetailsQuery) -> MatchDetails | None:
        with self.session_factory() as session:
            row = session.exec(
                select(TeamMatch, Team.name)
                .join(Team, Team.id == TeamMatch.team_id)
                .where(TeamMatch.id == query.team_match_id)
            ).first()
            if row is None:
                return None
            meeting, team_name = row
            result = MatchDetails(
                id=meeting.id,
                team_id=meeting.team_id,
                team_name=team_name,
                opponent_name=meeting.opponent_name,
                is_home=meeting.is_home,
                scheduled_at=meeting.scheduled_at,
                original_scheduled_at=meeting.original_scheduled_at,
                started_at=meeting.started_at,
                ended_at=meeting.ended_at,
                status=meeting.status,
                is_completed=meeting.is_completed,
                score_ttc=meeting.score_ttc,
                score_opponent=meeting.score_opponent,
                play_mode=meeting.play_mode,
                venue_name=meeting.venue_name,
                venue_street=meeting.venue_street,
                venue_city=meeting.venue_city,
                details_available=meeting.details_imported_at is not None,
                notices=[
                    MatchNotice(str(item.code), item.info)
                    for item in session.exec(
                        select(TeamMatchNotice)
                        .where(TeamMatchNotice.team_match_id == meeting.id)
                        .order_by(TeamMatchNotice.code)
                    ).all()
                ],
            )
            if not result.details_available:
                return result
            lineup = session.exec(
                select(MatchLineup)
                .where(MatchLineup.team_match_id == meeting.id)
                .order_by(
                    MatchLineup.position.asc().nulls_last(), MatchLineup.player_id
                )
            ).all()
            games = session.exec(
                select(Match)
                .where(Match.team_match_id == meeting.id)
                .order_by(Match.sequence, Match.id)
            ).all()
            participants = session.exec(
                select(MatchParticipant)
                .join(Match, Match.id == MatchParticipant.match_id)
                .where(Match.team_match_id == meeting.id)
                .order_by(MatchParticipant.match_id, MatchParticipant.player_id)
            ).all()
            sets = session.exec(
                select(SetResult)
                .join(Match, Match.id == SetResult.match_id)
                .where(Match.team_match_id == meeting.id)
                .order_by(SetResult.match_id, SetResult.set_number)
            ).all()
            player_ids = {item.player_id for item in lineup} | {
                item.player_id for item in participants
            }
            if self.players is None:
                raise RuntimeError(
                    "Spieler-Reader für Begegnungsdetails wurde nicht verdrahtet."
                )
            players = self.players.read_players(player_ids)
            result.lineup.extend(
                MatchLineupEntry(
                    players[item.player_id], item.position, item.doubles_pair
                )
                for item in lineup
            )
            participants_by_game = {}
            sets_by_game = {}
            for item in participants:
                participants_by_game.setdefault(item.match_id, []).append(item)
            for item in sets:
                sets_by_game.setdefault(item.match_id, []).append(
                    MatchSet(item.set_number, item.points_ttc, item.points_opponent)
                )
            for game in games:
                entries = participants_by_game.get(game.id, [])
                result.games.append(
                    MatchGame(
                        id=game.id,
                        sequence=game.sequence,
                        game_type=str(game.game_type),
                        name=game.match_name,
                        players=[players[item.player_id] for item in entries],
                        opponent_names=list(
                            dict.fromkeys(
                                item.opponent_name
                                for item in entries
                                if item.opponent_name
                            )
                        ),
                        sets=sets_by_game.get(game.id, []),
                    )
                )
            return result

    def get_team_lineup(self, query: GetTeamLineupQuery) -> TeamLineup | None:
        with self.session_factory() as session:
            team = session.get(Team, query.team_id)
            if team is None:
                return None
            assignments = session.exec(
                select(TeamAssignment)
                .where(TeamAssignment.team_id == team.id)
                .order_by(
                    TeamAssignment.position.asc().nulls_last(), TeamAssignment.player_id
                )
            ).all()
            result = TeamLineup(team.id, team.name, team.season_id, team.category)
            if not assignments:
                return result
            if self.players is None:
                raise RuntimeError(
                    "Spieler-Reader für die Aufstellung wurde nicht verdrahtet."
                )
            players = self.players.read_players(
                {item.player_id for item in assignments}
            )
            result.players.extend(
                TeamLineupEntry(
                    item.player_id,
                    players[item.player_id].first_name,
                    players[item.player_id].last_name,
                    item.position,
                    item.status,
                )
                for item in assignments
            )
            return result
