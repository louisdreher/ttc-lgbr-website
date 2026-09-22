from dataclasses import replace

from app.core.members.public import GetPlayerImages, GetPlayerImagesQuery
from app.core.competition.application.dto import (
    GetMatchDetailsQuery,
    GetScheduleQuery,
    GetTeamLineupQuery,
    GetTeamStandingsQuery,
    ListTeamsQuery,
    MatchDetails,
    ScheduledMatchSummary,
    SeasonSummary,
    StandingSummary,
    TeamLineup,
    TeamSummary,
)
from app.core.competition.application.errors import (
    MatchNotFoundError,
    TeamNotFoundError,
)
from app.core.competition.application.ports import CompetitionReader
from app.core.competition.application.dto import PlayerCandidate
from app.core.competition.domain.teams import RegistrationPosition, eligible_registration


class ListTeams:
    def __init__(self, reader: CompetitionReader):
        self.reader = reader

    def execute(self, query: ListTeamsQuery) -> list[TeamSummary]:
        return self.reader.list_teams(query)


class GetSchedule:
    def __init__(self, reader: CompetitionReader):
        self.reader = reader

    def execute(self, query: GetScheduleQuery) -> list[ScheduledMatchSummary]:
        if query.date_from > query.date_to:
            raise ValueError("Das Startdatum darf nicht nach dem Enddatum liegen.")
        return self.reader.get_schedule(query)


class GetTeamStandings:
    def __init__(self, reader: CompetitionReader):
        self.reader = reader

    def execute(self, query: GetTeamStandingsQuery) -> list[StandingSummary]:
        return self.reader.get_team_standings(query)


class GetMatchDetails:
    def __init__(self, reader: CompetitionReader):
        self.reader = reader

    def execute(self, query: GetMatchDetailsQuery) -> MatchDetails:
        result = self.reader.get_match_details(query)
        if result is None:
            raise MatchNotFoundError(query.team_match_id)
        return result


class GetTeamLineup:
    def __init__(self, reader: CompetitionReader, images: GetPlayerImages):
        self.reader = reader
        self.images = images

    def execute(self, query: GetTeamLineupQuery) -> TeamLineup:
        result = self.reader.get_team_lineup(query)
        if result is None:
            raise TeamNotFoundError(query.team_id)
        if not result.players:
            return result
        season = next(item for item in self.reader.list_seasons() if item.id == result.season_id)
        images = self.images.execute(GetPlayerImagesQuery(
            frozenset(player.player_id for player in result.players),
            season.start_year, season.half.value,
        ))
        return replace(result, players=[
            replace(player, media_id=images[player.player_id]) for player in result.players
        ])


class ListSeasons:
    def __init__(self, reader: CompetitionReader):
        self.reader = reader

    def execute(self) -> list[SeasonSummary]:
        return self.reader.list_seasons()


class GetTeamCandidates:
    def __init__(self, reader: CompetitionReader):
        self.reader = reader

    def execute(self, query: GetTeamLineupQuery) -> list[PlayerCandidate]:
        pool = self.reader.get_team_candidates(query.team_id)
        if pool is None:
            raise TeamNotFoundError(query.team_id)
        if not pool.category:
            return []
        ranks = eligible_registration(pool.team_number, [
            RegistrationPosition(item.player_id, item.team_number, item.rank)
            for item in pool.players
        ])
        candidates = {item.player_id: item for item in pool.players
                      if item.player_id in ranks and item.player_id not in pool.assigned_ids}
        return sorted(candidates.values(), key=lambda item: ranks[item.player_id])
