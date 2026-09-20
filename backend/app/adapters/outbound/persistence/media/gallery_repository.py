from dataclasses import replace

from sqlmodel import Session, select

from app.adapters.outbound.persistence.media.models import Gallery as GalleryRow
from app.adapters.outbound.persistence.media.models import GalleryMedia
from app.core.content.media.domain.gallery import Gallery


class SqlGalleryRepository:
    """Insert galleries in the caller's transaction; never commit or roll back."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def exists_for_event(self, event_id: int) -> bool:
        return self.session.exec(
            select(GalleryRow.id).where(GalleryRow.event_id == event_id)
        ).first() is not None

    def save(self, gallery: Gallery, *, created_by_user_id: int) -> Gallery:
        if gallery.id is not None:
            raise ValueError("This repository only inserts new galleries.")
        row = GalleryRow(
            title=gallery.title,
            gallery_date=gallery.gallery_date,
            show_date=gallery.show_date,
            event_id=gallery.event_id,
            cover_image_id=gallery.cover_image_id,
            created_by_user_id=created_by_user_id,
        )
        self.session.add(row)
        # Obtain the generated ID before inserting gallery memberships.
        self.session.flush()
        for position, media_id in enumerate(gallery.media_ids):
            self.session.add(GalleryMedia(
                gallery_id=row.id, media_asset_id=media_id, sort_order=position,
            ))
        self.session.flush()
        return replace(gallery, id=row.id)
