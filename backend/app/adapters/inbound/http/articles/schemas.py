from datetime import datetime

from app.core.content.articles.domain.article import (
    ArticleStatus,
    ArticleType,
    Visibility,
)
from pydantic import BaseModel, Field


class CreateArticleRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=255)
    teaser: str = ""
    content: str = Field(min_length=1)
    article_type: ArticleType = ArticleType.NEWS
    visibility: Visibility = Visibility.PUBLIC
    event_id: int | None = None


class CreatedArticleResponse(BaseModel):
    id: int
    title: str
    slug: str
    status: ArticleStatus


class ArticleVisibilityRequest(BaseModel):
    visibility: Visibility


class HiddenEventRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    starts_at: datetime
    category_id: int = Field(gt=0)
    ends_at: datetime | None = None
    location: str | None = None
    description: str | None = None


class SaveArticleRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    slug: str = Field(
        min_length=1, max_length=255, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$"
    )
    teaser: str = ""
    content: str = ""
    article_type: ArticleType = ArticleType.NEWS
    visibility: Visibility = Visibility.PUBLIC
    event_id: int | None = Field(default=None, gt=0)
    tags: list[str] = Field(default_factory=list, max_length=30)
    cover_image_id: int | None = Field(default=None, gt=0)
    new_event: HiddenEventRequest | None = None


class PublicArticleResponse(BaseModel):
    id: int
    author_name: str
    title: str
    slug: str
    teaser: str
    content: str
    article_type: ArticleType
    published_at: datetime | None
    tags: list[str]
    cover_image_id: int | None


class ArticleResponse(PublicArticleResponse):
    author_id: int
    visibility: Visibility
    status: ArticleStatus
    event_id: int | None
    updated_at: datetime
    system_authored: bool
    generated: bool
    allowed_actions: list[str]


class PublicArticlePageResponse(BaseModel):
    items: list[PublicArticleResponse]
    total: int
    offset: int
    limit: int


class ArticlePageResponse(BaseModel):
    items: list[ArticleResponse]
    total: int
    offset: int
    limit: int


class OpportunityResponse(BaseModel):
    event_id: int
    title: str
    starts_at: datetime
    team_match_id: int | None
    article_id: int | None


class OpportunityPageResponse(BaseModel):
    team_matches: list[OpportunityResponse]
    other_events: list[OpportunityResponse]
    total: int
    offset: int
    limit: int


class PreparedArticleResponse(BaseModel):
    article_id: int | None
    event_id: int
    title: str
    slug: str
    teaser: str
    content: str
    article_type: ArticleType
    visibility: Visibility
    tags: list[str]
    cover_image_id: int | None
    editable_fields: list[str]
