from pydantic import BaseModel, Field

from app.core.content.articles.domain.article import (
    ArticleStatus,
    ArticleType,
    Visibility,
)


class CreateArticleRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=255)
    teaser: str = Field(min_length=1)
    content: str = Field(min_length=1)
    article_type: ArticleType = ArticleType.NEWS
    visibility: Visibility = Visibility.PUBLIC
    event_id: int | None = None


class CreatedArticleResponse(BaseModel):
    id: int
    title: str
    slug: str
    status: ArticleStatus
