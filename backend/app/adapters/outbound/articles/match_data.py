from collections.abc import Callable

from app.core.competition.public import GetMatchDetails, GetMatchDetailsQuery
from app.core.content.articles.application.dto import MatchReportData
from app.core.content.articles.domain.article import Visibility
from app.core.content.events.public import EventDetails


class CompetitionMatchReportReader:
    def __init__(
        self, matches: GetMatchDetails, events: Callable[[int], EventDetails | None]
    ):
        self.matches, self.events = matches, events

    def read(self, team_match_id: int) -> MatchReportData:
        match = self.matches.execute(GetMatchDetailsQuery(team_match_id))
        event = self.events(team_match_id)
        return MatchReportData(
            match=match,
            event_id=event.id if event else None,
            report_expected=event.report_expected if event else False,
            visibility=Visibility(event.visibility.value)
            if event
            else Visibility.HIDDEN,
        )
