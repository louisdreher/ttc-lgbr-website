from dataclasses import asdict

from app.core.competition.public import GetMatchDetails, GetMatchDetailsQuery
from app.core.content.articles.application.dto import (
    ArticleEventContext,
    HiddenEventInput,
)
from app.core.content.articles.application.errors import ArticleNotFoundError
from app.core.content.articles.domain.slugs import match_report_slug
from app.core.content.events.public import (
    CreateEventCommand,
    CreateHiddenEditorialEvent,
    EventReader,
)


class EventArticleContext:
    def __init__(
        self,
        reader: EventReader,
        creator: CreateHiddenEditorialEvent,
        matches: GetMatchDetails,
    ):
        self.reader, self.creator = reader, creator
        self.matches = matches

    def get(self, event_id: int) -> ArticleEventContext:
        event = self.reader.get(event_id)
        if event is None:
            raise ArticleNotFoundError("Event nicht gefunden.")
        slug = None
        if event.team_match_id is not None:
            match = self.matches.execute(GetMatchDetailsQuery(event.team_match_id))
            slug = match_report_slug(
                match.team_name, match.team_number, match.scheduled_at
            )
        return ArticleEventContext(
            event.id, event.title, event.description or "", event.team_match_id, slug
        )

    def create_hidden(self, values: HiddenEventInput, author_id: int) -> int:
        return self.creator.execute(
            CreateEventCommand(**asdict(values), created_by_user_id=author_id)
        )
