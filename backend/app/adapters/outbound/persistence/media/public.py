"""Public persistence contract for using event-gallery images in reports."""
from sqlmodel import Session, select
from app.adapters.outbound.persistence.media.models import Gallery, GalleryMedia
from app.adapters.outbound.persistence.media.gallery_repository import SqlGalleryRepository


def event_gallery_contains_image(session: Session, event_id: int, media_id: int) -> bool:
    # Report writes already hold the event lock. Keep membership stable until commit.
    gallery = session.exec(select(Gallery).where(Gallery.event_id == event_id).with_for_update()).first()
    return gallery is not None and session.get(GalleryMedia, (gallery.id, media_id)) is not None


def adopt_report_cover(session: Session, event_id: int, media_id: int) -> None:
    """Adopt an authorized report cover in the caller's transaction.

    Caller validates the cover and locks event then report. Gallery creation
    follows that same lock order; editing an existing gallery locks its row.
    """
    gallery_id = session.exec(select(Gallery.id).where(Gallery.event_id == event_id)).first()
    if gallery_id is None:
        return
    repository = SqlGalleryRepository(session)
    snapshot = repository.get_for_update(gallery_id)
    if snapshot is None:
        return
    updated = snapshot.gallery.add_image(media_id).set_cover(media_id)
    if updated != snapshot.gallery:
        # Also advances updated_at: an already open gallery form must reload.
        repository.update(updated)
