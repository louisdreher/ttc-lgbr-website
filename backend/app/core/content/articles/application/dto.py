from dataclasses import dataclass

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
