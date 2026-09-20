from datetime import datetime

from sqlmodel import Session, select

from app.adapters.outbound.persistence.events.models import Event


class SqlGalleryEventReader:
    def __init__(self, session: Session):
        self.session = session

    def lock_for_gallery(self, event_id: int) -> datetime | None:
        row = self.session.exec(
            select(Event).where(Event.id == event_id).with_for_update()
            .execution_options(populate_existing=True)
        ).first()
        return row.starts_at if row is not None else None
