"""Article context exposed to gallery creation without persistence dependencies."""

from dataclasses import dataclass
from typing import Protocol

from app.core.content.articles.domain.article import ArticleStatus


@dataclass(frozen=True)
class GalleryReportContext:
    author_id: int
    status: ArticleStatus
    system_authored: bool
    cover_image_id: int | None

    def editable_by_writer(self, user_id: int) -> bool:
        if self.system_authored:
            return self.status == ArticleStatus.DRAFT
        return self.author_id == user_id and self.status in (
            ArticleStatus.DRAFT, ArticleStatus.IN_REVIEW,
        )


class GalleryReportReader(Protocol):
    def lock_for_gallery(self, event_id: int) -> GalleryReportContext | None:
        """Lock an existing report; caller must first lock its event."""
        ...
