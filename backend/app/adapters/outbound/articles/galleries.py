from sqlmodel import Session

from app.adapters.outbound.persistence.media.public import adopt_report_cover


class SqlArticleGalleryCovers:
    """Bridge the article port to media's public, transaction-local contract."""

    def __init__(self, session: Session):
        self.session = session

    def adopt(self, event_id: int, media_id: int) -> None:
        adopt_report_cover(self.session, event_id, media_id)
