from dataclasses import dataclass

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
