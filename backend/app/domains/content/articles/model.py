from datetime import datetime, timezone
from enum import StrEnum

import sqlalchemy as sa
from app.domains.content.types import Visibility
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ArticleStatus(StrEnum):
    DRAFT = "DRAFT"
    IN_REVIEW = "IN_REVIEW"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class ArticleType(StrEnum):
    NEWS = "NEWS"
    MATCH_REPORT = "MATCH_REPORT"
    EVENT_REPORT = "EVENT_REPORT"
    ANNUAL_REPORT = "ANNUAL_REPORT"
    ANNOUNCEMENT = "ANNOUNCEMENT"


class Tag(SQLModel, table=True):
    __tablename__ = "tag"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    slug: str = Field(unique=True, index=True)
    is_active: bool = True
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_type=sa.DateTime(timezone=True),
    )


class ArticleTag(SQLModel, table=True):
    __tablename__ = "article_tag"

    article_id: int = Field(
        foreign_key="article.id",
        ondelete="CASCADE",
        primary_key=True,
    )
    tag_id: int = Field(
        foreign_key="tag.id",
        ondelete="CASCADE",
        primary_key=True,
    )


class Article(SQLModel, table=True):
    __tablename__ = "article"

    id: int | None = Field(default=None, primary_key=True)
    event_id: int | None = Field(
        default=None,
        foreign_key="event.id",
        ondelete="SET NULL",
        index=True,
    )
    author_id: int = Field(
        foreign_key="user.id",
        index=True,
    )
    title: str
    slug: str = Field(unique=True, index=True)
    teaser: str
    content: str
    cover_image_id: int | None = Field(
        default=None,
        foreign_key="media_asset.id",
        ondelete="SET NULL",
    )
    status: ArticleStatus = Field(
        default=ArticleStatus.DRAFT,
        sa_type=sa.Enum(ArticleStatus, name="article_status"),
        index=True,
    )
    article_type: ArticleType = Field(
        default=ArticleType.NEWS,
        sa_type=sa.Enum(ArticleType, name="article_type"),
        index=True,
    )
    visibility: Visibility = Field(
        default=Visibility.PUBLIC,
        sa_type=sa.Enum(Visibility, name="content_visibility"),
        index=True,
    )
    published_at: datetime | None = Field(
        default=None,
        sa_type=sa.DateTime(timezone=True),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_type=sa.DateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_type=sa.DateTime(timezone=True),
    )
