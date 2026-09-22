from datetime import timezone
from dataclasses import asdict
from zoneinfo import ZoneInfo

from app.core.content.articles.public import GalleryReportReader
from app.core.content.events.public import GalleryEventReader, CreateHiddenEditorialEvent, CreateEventCommand, EventServiceError
from app.core.content.media.application.dto import GalleryEventContext, GalleryNewEvent
from app.core.content.media.domain.gallery import GalleryError


class EventGalleryContext:
    def __init__(self, events: GalleryEventReader, reports: GalleryReportReader, creator: CreateHiddenEditorialEvent):
        self.events, self.reports = events, reports
        self.creator = creator

    def create_hidden(self, values: GalleryNewEvent, user_id: int) -> int:
        try:
            return self.creator.execute(CreateEventCommand(**asdict(values), created_by_user_id=user_id))
        except EventServiceError as error:
            raise GalleryError(str(error)) from error

    def for_creation(self, event_id: int, user_id: int) -> GalleryEventContext | None:
        starts_at = self.events.lock_for_gallery(event_id)
        if starts_at is None:
            return None
        report = self.reports.lock_for_gallery(event_id)
        # SQLite loses timezone information; persisted timestamps represent UTC.
        if starts_at.tzinfo is None:
            starts_at = starts_at.replace(tzinfo=timezone.utc)
        return GalleryEventContext(
            can_edit_report=report is not None and report.editable_by_writer(user_id),
            report_cover_image_id=report.cover_image_id if report else None,
            event_date=starts_at.astimezone(ZoneInfo("Europe/Berlin")).date(),
        )
