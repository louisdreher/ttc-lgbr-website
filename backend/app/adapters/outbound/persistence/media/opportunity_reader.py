from sqlalchemy import func
from sqlmodel import Session, select

from app.adapters.outbound.persistence.events.public import past_report_events
from app.adapters.outbound.persistence.media.models import Gallery
from app.core.content.media.application.dto import (
    GalleryOpportunitiesQuery, GalleryOpportunity, GalleryOpportunityPage,
)


class SqlGalleryOpportunityReader:
    def __init__(self, session: Session):
        self.session = session

    def opportunities(self, query: GalleryOpportunitiesQuery) -> GalleryOpportunityPage:
        events = past_report_events(query.as_of).subquery()
        base = select(events).outerjoin(
            Gallery, Gallery.event_id == events.c.event_id,
        ).where(Gallery.id.is_(None))
        base = base.where(
            events.c.team_match_id.is_not(None) if query.group == "team_matches"
            else events.c.team_match_id.is_(None)
        )
        total = self.session.exec(select(func.count()).select_from(base.subquery())).one()
        rows = self.session.execute(
            base.order_by(events.c.starts_at.desc(), events.c.event_id.desc())
            .offset(query.offset).limit(query.limit)
        ).mappings().all()
        return GalleryOpportunityPage(
            tuple(GalleryOpportunity(**row) for row in rows), total, query.offset, query.limit,
        )
