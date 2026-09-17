from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.core.competition.public import MatchDetails
from app.core.content.articles.domain.article import (
    ArticleStatus,
    ArticleType,
    Visibility,
)


@dataclass(frozen=True)
class CreateArticleCommand:
    author_id: int
    title: str
    slug: str
    teaser: str
    content: str
    article_type: ArticleType
    visibility: Visibility
    event_id: int | None = None


@dataclass(frozen=True)
class CreatedArticle:
    id: int
    title: str
    slug: str
    status: ArticleStatus


@dataclass(frozen=True)
class CreateMatchReportDraftCommand:
    team_match_id: int
    # None means a trusted automatic invocation using the system author.
    author_id: int | None = None
    require_report_expected: bool = False


@dataclass(frozen=True)
class MatchReportData:
    match: MatchDetails
    event_id: int | None
    report_expected: bool
    visibility: Visibility


@dataclass(frozen=True)
class GeneratedMatchReport:
    title: str
    teaser: str
    content: str
    method: str


@dataclass(frozen=True)
class MatchReportDraftResult:
    article_id: int | None
    created: bool
    reason: str


@dataclass(frozen=True)
class EditArticleDraftCommand:
    article_id: int
    author_id: int
    title: str
    teaser: str
    content: str


@dataclass(frozen=True)
class ArticleActor:
    user_id: int | None = None
    can_write: bool = False
    can_edit_all: bool = False
    authenticated: bool = False


@dataclass(frozen=True, kw_only=True)
class HiddenEventInput:
    title: str
    starts_at: datetime
    category_id: int
    ends_at: datetime | None = None
    location: str | None = None
    description: str | None = None


@dataclass(frozen=True, kw_only=True)
class SaveArticleCommand:
    actor: ArticleActor
    title: str
    slug: str
    teaser: str = ""
    content: str = ""
    article_type: ArticleType = ArticleType.NEWS
    visibility: Visibility = Visibility.PUBLIC
    article_id: int | None = None
    event_id: int | None = None
    tags: tuple[str, ...] = ()
    cover_image_id: int | None = None
    new_event: HiddenEventInput | None = None


@dataclass(frozen=True)
class PublishArticleCommand:
    actor: ArticleActor
    article_id: int


@dataclass(frozen=True)
class ManageArticleCommand:
    actor: ArticleActor
    article_id: int
    action: Literal["visibility", "archive", "restore", "delete"]
    visibility: Visibility | None = None


@dataclass(frozen=True, kw_only=True)
class ListArticlesQuery:
    actor: ArticleActor
    scope: str = "mine"
    statuses: tuple[ArticleStatus, ...] = ()
    article_type: ArticleType | None = None
    offset: int = 0
    limit: int = 20
    updated_since: datetime | None = None


@dataclass(frozen=True, kw_only=True)
class GetArticleQuery:
    actor: ArticleActor
    article_id: int | None = None
    slug: str | None = None
    scope: str = "cms"


@dataclass(frozen=True)
class EventArticleQuery:
    actor: ArticleActor
    event_id: int


@dataclass(frozen=True, kw_only=True)
class OpportunityQuery:
    actor: ArticleActor
    offset: int = 0
    limit: int = 50


@dataclass(frozen=True, kw_only=True)
class ArticleDetails:
    id: int
    author_id: int
    author_name: str
    title: str
    slug: str
    teaser: str
    content: str
    article_type: ArticleType
    visibility: Visibility
    status: ArticleStatus
    event_id: int | None
    published_at: datetime | None
    updated_at: datetime
    tags: tuple[str, ...]
    cover_image_id: int | None
    system_authored: bool
    generated: bool
    allowed_actions: tuple[str, ...] = ()


@dataclass(frozen=True)
class ArticlePage:
    items: tuple[ArticleDetails, ...]
    total: int
    offset: int
    limit: int


@dataclass(frozen=True)
class ArticleOpportunity:
    event_id: int
    title: str
    starts_at: datetime
    team_match_id: int | None
    article_id: int | None


@dataclass(frozen=True)
class OpportunityPage:
    team_matches: tuple[ArticleOpportunity, ...]
    other_events: tuple[ArticleOpportunity, ...]
    total: int
    offset: int
    limit: int


@dataclass(frozen=True)
class ArticleEventContext:
    event_id: int
    title: str
    description: str
    team_match_id: int | None
    match_slug: str | None = None


@dataclass(frozen=True)
class PreparedArticle:
    article_id: int | None
    event_id: int
    title: str
    slug: str
    teaser: str
    content: str
    article_type: ArticleType
    visibility: Visibility
    tags: tuple[str, ...]
    cover_image_id: int | None
    editable_fields: tuple[str, ...]
