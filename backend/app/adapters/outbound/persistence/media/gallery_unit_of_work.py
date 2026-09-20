from sqlmodel import Session
from sqlalchemy.exc import IntegrityError

from app.adapters.outbound.persistence.media.gallery_repository import SqlGalleryRepository
from app.adapters.outbound.persistence.media.repository import SqlMediaRepository
from app.core.content.media.application.ports import GalleryEvents
from app.core.content.media.application.errors import EventGalleryAlreadyExists


class SqlGalleryUnitOfWork:
    """Caller owns the session; all collaborators must share this transaction."""

    def __init__(self, session: Session, events: GalleryEvents):
        self.session = session
        self.galleries = SqlGalleryRepository(session)
        self.media = SqlMediaRepository(session)
        self.events = events
        self._committed = False

    def __enter__(self):
        self._committed = False
        return self

    def commit(self) -> None:
        self.session.commit()
        self._committed = True

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if exc_type is not None or not self._committed:
            self.session.rollback()
        if isinstance(exc_value, IntegrityError):
            diagnostic = getattr(exc_value.orig, "diag", None)
            if getattr(diagnostic, "constraint_name", None) == "ix_gallery_event_id":
                raise EventGalleryAlreadyExists(
                    "Für dieses Event existiert bereits eine Galerie."
                ) from exc_value
