from dataclasses import replace
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.adapters.outbound.persistence.media.models import Gallery as GalleryRow
from app.adapters.outbound.persistence.media.models import GalleryMedia
from app.core.content.media.domain.gallery import Gallery
from app.core.content.media.application.dto import GallerySnapshot


class SqlGalleryRepository:
    """Insert galleries in the caller's transaction; never commit or roll back."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def exists_for_event(self, event_id: int) -> bool:
        return self.session.exec(
            select(GalleryRow.id).where(GalleryRow.event_id == event_id)
        ).first() is not None

    def get_for_update(self, gallery_id: int) -> GallerySnapshot | None:
        row = self.session.exec(select(GalleryRow).where(GalleryRow.id == gallery_id)
            .with_for_update().execution_options(populate_existing=True)).first()
        if row is None:
            return None
        ids = tuple(self.session.exec(select(GalleryMedia.media_asset_id)
            .where(GalleryMedia.gallery_id == gallery_id)
            .order_by(GalleryMedia.sort_order, GalleryMedia.media_asset_id)).all())
        return GallerySnapshot(Gallery(id=row.id, title=row.title, event_id=row.event_id,
            gallery_date=row.gallery_date, show_date=row.show_date, media_ids=ids,
            cover_image_id=row.cover_image_id), row.created_by_user_id, row.updated_at)

    def update(self, gallery: Gallery) -> None:
        row = self.session.get(GalleryRow, gallery.id)
        row.title, row.gallery_date, row.show_date = gallery.title, gallery.gallery_date, gallery.show_date
        row.cover_image_id = gallery.cover_image_id
        row.updated_at = datetime.now(timezone.utc)
        members = self.session.exec(select(GalleryMedia).where(GalleryMedia.gallery_id == gallery.id)).all()
        existing = {item.media_asset_id: item for item in members}
        for item in members:
            if item.media_asset_id not in gallery.media_ids:
                self.session.delete(item)
        for position, media_id in enumerate(gallery.media_ids):
            item = existing.get(media_id) or GalleryMedia(gallery_id=gallery.id, media_asset_id=media_id)
            item.sort_order = position
            self.session.add(item)
        self.session.add(row)
        self.session.flush()

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
