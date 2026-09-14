from app.core.competition.application.dto import (
    GetMatchDetailsQuery,
    GetScheduleQuery,
    GetTeamLineupQuery,
    GetTeamStandingsQuery,
    ListTeamsQuery,
    MatchDetails,
    ScheduledMatchSummary,
    StandingSummary,
    TeamLineup,
    TeamSummary,
)
from app.core.competition.application.errors import (
    MatchNotFoundError,
    TeamNotFoundError,
)
from app.core.competition.application.ports import CompetitionReader


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
    def __init__(self, reader: CompetitionReader):
        self.reader = reader

    def execute(self, query: GetTeamLineupQuery) -> TeamLineup:
        result = self.reader.get_team_lineup(query)
        if result is None:
            raise TeamNotFoundError(query.team_id)
        return result
