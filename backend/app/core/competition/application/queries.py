from app.core.competition.application.dto import (
    ListTeamsQuery,
    TeamSummary,
)
from app.core.competition.application.ports import CompetitionReader


class ListTeams:
    def __init__(self, reader: CompetitionReader):
        self.reader = reader

    def execute(self, query: ListTeamsQuery) -> list[TeamSummary]:
        return self.reader.list_teams(query)
