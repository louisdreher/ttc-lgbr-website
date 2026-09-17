from dataclasses import replace

from app.core.content.articles.application.access import (
    actions,
    require_editor,
    require_writer,
)
from app.core.content.articles.application.dto import (
    ArticlePage,
    EventArticleQuery,
    GetArticleQuery,
    ListArticlesQuery,
    OpportunityQuery,
    PreparedArticle,
)
from app.core.content.articles.application.errors import (
    ArticleAuthorError,
    ArticleConflictError,
    ArticleNotFoundError,
)
from app.core.content.articles.application.ports import ArticleEvents, ArticleReader
from app.core.content.articles.domain.article import (
    ArticleStatus,
    ArticleType,
    Visibility,
)


def pagination(offset: int, limit: int) -> None:
    if offset < 0 or not 1 <= limit <= 100:
        raise ValueError("Ungültige Seitennavigation.")


class ListArticles:
    def __init__(self, reader: ArticleReader):
        self.reader = reader

    def execute(self, query: ListArticlesQuery) -> ArticlePage:
        pagination(query.offset, query.limit)
        if query.scope == "mine":
            require_writer(query.actor)
        elif query.scope == "editorial":
            require_editor(query.actor)
        elif query.scope == "members":
            if not query.actor.authenticated:
                raise ArticleAuthorError("Anmeldung erforderlich.")
        elif query.scope != "public":
            raise ValueError("Unbekannte Artikelansicht.")
        page = self.reader.list(query)
        return replace(
            page,
            items=tuple(
                replace(a, allowed_actions=actions(query.actor, a)) for a in page.items
            ),
        )


class GetArticle:
    def __init__(self, reader: ArticleReader):
        self.reader = reader

    def execute(self, query: GetArticleQuery):
        if (query.article_id is None) == (query.slug is None):
            raise ValueError("Genau eine Artikel-ID oder ein Slug ist erforderlich.")
        article = self.reader.get(article_id=query.article_id, slug=query.slug)
        if article is None:
            raise ArticleNotFoundError("Beitrag nicht gefunden.")
        if query.scope == "cms":
            require_writer(query.actor)
            visible = (
                query.actor.can_edit_all
                or article.author_id == query.actor.user_id
                or (article.system_authored and article.status == ArticleStatus.DRAFT)
            )
        elif query.scope in ("public", "members"):
            if query.scope == "members" and not query.actor.authenticated:
                raise ArticleAuthorError("Anmeldung erforderlich.")
            visible = article.status == ArticleStatus.PUBLISHED and (
                article.visibility == Visibility.PUBLIC
                or (
                    query.scope == "members"
                    and article.visibility == Visibility.MEMBERS_ONLY
                )
            )
        else:
            raise ValueError("Unbekannte Artikelansicht.")
        if not visible:
            raise ArticleNotFoundError("Beitrag nicht gefunden.")
        return replace(article, allowed_actions=actions(query.actor, article))


class ListArticleOpportunities:
    def __init__(self, reader: ArticleReader):
        self.reader = reader

    def execute(self, query: OpportunityQuery):
        require_writer(query.actor)
        pagination(query.offset, query.limit)
        return self.reader.opportunities(query)


class PrepareArticleForEvent:
    def __init__(self, reader: ArticleReader, events: ArticleEvents):
        self.reader, self.events = reader, events

    def execute(self, query: EventArticleQuery) -> PreparedArticle:
        require_writer(query.actor)
        event = self.events.get(query.event_id)
        article = self.reader.get(event_id=query.event_id)
        if (
            article is not None
            and not (article.status == ArticleStatus.DRAFT and article.system_authored)
            and article.author_id != query.actor.user_id
        ):
            raise ArticleConflictError(
                "Für diesen Event wurde bereits ein Beitrag übernommen."
            )
        fields = (
            "title",
            "slug",
            "teaser",
            "content",
            "visibility",
            "tags",
            "cover_image_id",
        )
        if event.team_match_id is None:
            fields += ("article_type",)
        else:
            fields = tuple(field for field in fields if field != "slug")
        if article is not None:
            if "save" not in actions(query.actor, article):
                fields = ()
            return PreparedArticle(
                article.id,
                event.event_id,
                article.title,
                event.match_slug
                if article.system_authored and event.match_slug
                else article.slug,
                article.teaser,
                article.content,
                article.article_type,
                article.visibility,
                article.tags,
                article.cover_image_id,
                fields,
            )
        return PreparedArticle(
            None,
            event.event_id,
            event.title,
            event.match_slug or f"bericht-{event.event_id}",
            "",
            event.description,
            ArticleType.MATCH_REPORT
            if event.team_match_id
            else ArticleType.EVENT_REPORT,
            Visibility.PUBLIC,
            (),
            None,
            fields,
        )
