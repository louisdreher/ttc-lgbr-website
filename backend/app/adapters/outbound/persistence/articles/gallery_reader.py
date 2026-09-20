from sqlmodel import Session, select

from app.adapters.outbound.persistence.articles.models import Article
from app.core.content.articles.public import GalleryReportContext, ArticleStatus
from app.core.users.public import UserReader


class SqlGalleryReportReader:
    def __init__(self, session: Session, users: UserReader):
        self.session, self.users = session, users

    def lock_for_gallery(self, event_id: int) -> GalleryReportContext | None:
        row = self.session.exec(
            select(Article).where(Article.event_id == event_id).with_for_update()
            .execution_options(populate_existing=True)
        ).first()
        if row is None:
            return None
        return GalleryReportContext(
            author_id=row.author_id, status=ArticleStatus(row.status),
            system_authored=row.author_id == self.users.get_system_author_id(),
            cover_image_id=row.cover_image_id,
        )
