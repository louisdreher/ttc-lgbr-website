from typing import Protocol, Self

from app.core.content.articles.application.dto import (
    ArticleDetails,
    ArticleEventContext,
    ArticlePage,
    GeneratedMatchReport,
    HiddenEventInput,
    ListArticlesQuery,
    MatchReportData,
    OpportunityPage,
    OpportunityQuery,
)
from app.core.content.articles.domain.article import Article


class ArticleRepository(Protocol):
    def slug_exists(self, slug: str) -> bool: ...

    def save(self, article: Article) -> Article: ...
    def get(self, article_id: int, *, for_update: bool = False) -> Article | None: ...
    def lock_generation(self, team_match_id: int) -> None: ...
    def find_match_report(self, key: str, event_id: int | None) -> Article | None: ...
    def find_by_event(self, event_id: int) -> Article | None: ...
    def lock_event(self, event_id: int) -> None: ...
    def validate_cover(
        self, cover_image_id: int | None, *, user_id: int, can_edit_all: bool, event_id: int | None = None
    ) -> None: ...
    def delete(self, article: Article) -> None: ...


class ArticleGalleryCovers(Protocol):
    def adopt(self, event_id: int, media_id: int) -> None:
        """Adopt a validated report cover into an existing gallery, without committing.

        The caller holds the event/report locks. Never create a gallery here.
        """
        ...


class ArticleUnitOfWork(Protocol):
    articles: ArticleRepository
    gallery_covers: ArticleGalleryCovers

    def __enter__(self) -> Self: ...
    def __exit__(self, exc_type, exc_value, traceback) -> None: ...
    def commit(self) -> None: ...


class MatchReportReader(Protocol):
    def read(self, team_match_id: int) -> MatchReportData: ...


class MatchReportGenerator(Protocol):
    def generate(self, data: MatchReportData) -> GeneratedMatchReport: ...


class ArticleAuthors(Protocol):
    def system_id(self) -> int: ...
    def ensure_editor(self, user_id: int) -> None: ...


class ArticleReader(Protocol):
    def get(
        self,
        *,
        article_id: int | None = None,
        slug: str | None = None,
        event_id: int | None = None,
    ) -> ArticleDetails | None: ...
    def list(self, query: ListArticlesQuery) -> ArticlePage: ...
    def opportunities(self, query: OpportunityQuery) -> OpportunityPage: ...


class ArticleEvents(Protocol):
    def get(self, event_id: int) -> ArticleEventContext: ...
    def create_hidden(self, values: HiddenEventInput, author_id: int) -> int: ...
