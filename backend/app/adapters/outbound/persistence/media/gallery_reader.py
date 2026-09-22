from datetime import timezone
from sqlalchemy import func, extract
from sqlmodel import Session, select
from app.adapters.outbound.persistence.media.models import Gallery, GalleryMedia
from app.core.content.media.application.dto import GallerySummary, GalleryDetails, GalleryPage, ListGalleriesQuery


class SqlGalleryReader:
    def __init__(self, session: Session):
        self.session = session

    def find_by_event(self, event_id: int) -> GalleryDetails | None:
        gallery_id = self.session.exec(select(Gallery.id).where(Gallery.event_id == event_id)).first()
        return self.get(gallery_id) if gallery_id is not None else None

    def list(self, query: ListGalleriesQuery) -> GalleryPage:
        access = [] if query.can_manage_media else [Gallery.created_by_user_id == query.user_id]
        years = self.session.exec(select(extract('year', Gallery.gallery_date)).where(*access)
            .distinct().order_by(extract('year', Gallery.gallery_date).desc())).all()
        conditions = list(access)
        if query.year is not None:
            conditions.append(extract('year', Gallery.gallery_date) == query.year)
        total = self.session.exec(select(func.count()).select_from(Gallery).where(*conditions)).one()
        rows = self.session.exec(select(Gallery, func.count(GalleryMedia.media_asset_id))
            .outerjoin(GalleryMedia, GalleryMedia.gallery_id == Gallery.id).where(*conditions)
            .group_by(Gallery.id).order_by(Gallery.gallery_date.desc(), Gallery.id.desc())
            .offset(query.offset).limit(query.limit)).all()
        return GalleryPage(tuple(GallerySummary(id=g.id, title=g.title, event_id=g.event_id,
            gallery_date=g.gallery_date, show_date=g.show_date, cover_image_id=g.cover_image_id,
            image_count=count) for g, count in rows), total, query.offset, query.limit, tuple(int(y) for y in years))

    def get(self, gallery_id: int) -> GalleryDetails | None:
        g = self.session.get(Gallery, gallery_id, populate_existing=True)
        if g is None:
            return None
        ids = tuple(self.session.exec(select(GalleryMedia.media_asset_id).where(GalleryMedia.gallery_id == gallery_id)
            .order_by(GalleryMedia.sort_order, GalleryMedia.media_asset_id)).all())
        return GalleryDetails(id=g.id, title=g.title, event_id=g.event_id, gallery_date=g.gallery_date,
            show_date=g.show_date, cover_image_id=g.cover_image_id, image_count=len(ids), media_ids=ids,
            created_by_user_id=g.created_by_user_id,
            updated_at=g.updated_at if g.updated_at.tzinfo else g.updated_at.replace(tzinfo=timezone.utc))
