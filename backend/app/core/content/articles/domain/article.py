from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum

from .errors import ArticleDomainError, EmptyArticleFieldError


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


class Visibility(StrEnum):
    PUBLIC = "PUBLIC"
    MEMBERS_ONLY = "MEMBERS_ONLY"
    HIDDEN = "HIDDEN"


@dataclass
class Article:
    id: int | None
    author_id: int
    title: str
    slug: str
    teaser: str
    content: str
    article_type: ArticleType
    visibility: Visibility
    status: ArticleStatus
    event_id: int | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime
    generation_key: str | None = None
    generation_method: str | None = None
    generated_at: datetime | None = None
    tags: list[str] = field(default_factory=list)
    cover_image_id: int | None = None

    def revise(
        self,
        *,
        title: str,
        slug: str,
        teaser: str,
        content: str,
        article_type: ArticleType,
        visibility: Visibility,
        tags: list[str],
        cover_image_id: int | None,
    ) -> None:
        if self.status == ArticleStatus.ARCHIVED:
            raise ArticleDomainError("Archivierte Beiträge sind nicht bearbeitbar.")
        self.title = self._required_text(title, "Der Titel")
        self.slug = self._required_text(slug, "Der Slug").lower()
        self.teaser, self.content = teaser.strip(), content.strip()
        self.article_type, self.visibility = article_type, visibility
        self.tags = list(
            dict.fromkeys(self._required_text(tag, "Das Tag").lower() for tag in tags)
        )
        self.cover_image_id = cover_image_id
        if self.status in (ArticleStatus.IN_REVIEW, ArticleStatus.PUBLISHED):
            self.ensure_ready()
        self.updated_at = utc_now()

    def ensure_ready(self) -> None:
        self._required_text(self.title, "Der Titel")
        self._required_text(self.content, "Der Inhalt")

    def submit(self) -> None:
        if self.status not in (ArticleStatus.DRAFT, ArticleStatus.IN_REVIEW):
            raise ArticleDomainError(
                "Nur unveröffentlichte Beiträge können eingereicht werden."
            )
        self.ensure_ready()
        self.status = ArticleStatus.IN_REVIEW
        self.updated_at = utc_now()

    def publish(self) -> None:
        if self.status not in (ArticleStatus.DRAFT, ArticleStatus.IN_REVIEW):
            raise ArticleDomainError("Dieser Beitrag kann nicht veröffentlicht werden.")
        self.ensure_ready()
        self.status = ArticleStatus.PUBLISHED
        self.published_at = self.updated_at = utc_now()

    def archive(self) -> None:
        self.status = ArticleStatus.ARCHIVED
        self.updated_at = utc_now()

    def restore(self) -> None:
        if self.status != ArticleStatus.ARCHIVED:
            raise ArticleDomainError(
                "Nur archivierte Beiträge können wiederhergestellt werden."
            )
        self.status = ArticleStatus.DRAFT
        self.published_at = None
        self.updated_at = utc_now()

    def change_visibility(self, visibility: Visibility) -> None:
        self.visibility = visibility
        self.updated_at = utc_now()

    def edit_draft(
        self, *, author_id: int, title: str, teaser: str, content: str
    ) -> None:
        if self.status != ArticleStatus.DRAFT:
            raise ArticleDomainError("Nur Entwürfe dürfen hier bearbeitet werden.")
        title = self._required_text(title, "Der Titel")
        teaser = teaser.strip()
        content = self._required_text(content, "Der Inhalt")
        self.title, self.teaser, self.content = title, teaser, content
        self.author_id = author_id
        self.updated_at = utc_now()

    @classmethod
    def create_draft(
        cls,
        *,
        author_id: int,
        title: str,
        slug: str,
        teaser: str,
        content: str,
        article_type: ArticleType,
        visibility: Visibility,
        event_id: int | None = None,
    ) -> "Article":
        now = utc_now()

        return cls(
            id=None,
            author_id=author_id,
            title=cls._required_text(title, "Der Titel"),
            slug=cls._required_text(slug, "Der Slug").lower(),
            teaser=teaser.strip(),
            content=cls._required_text(content, "Der Inhalt"),
            article_type=article_type,
            visibility=visibility,
            status=ArticleStatus.DRAFT,
            event_id=event_id,
            published_at=None,
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def _required_text(
        value: str,
        field_name: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise EmptyArticleFieldError(field_name)

        return normalized


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
