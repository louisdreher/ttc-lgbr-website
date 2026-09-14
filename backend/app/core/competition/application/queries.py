from app.core.competition.application.dto import (
    GetScheduleQuery,
    ListTeamsQuery,
    ScheduledMatchSummary,
    TeamSummary,
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
