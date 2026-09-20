from pathlib import Path

from sqlmodel import Session

from app.adapters.outbound.media.image_processor import PillowImageProcessor
from app.adapters.outbound.media.local_storage import LocalMediaStorage
from app.adapters.outbound.persistence.media.unit_of_work import SqlMediaUnitOfWork
from app.core.content.media.application.commands import UpdateCaption, UploadImage
from app.core.content.media.application.queries import GetCaption, GetImage
from app.adapters.outbound.persistence.media.reader import SqlMediaReader
from app.adapters.outbound.persistence.media.opportunity_reader import SqlGalleryOpportunityReader
from app.core.content.media.application.queries import ListGalleryOpportunities


def build_gallery_opportunities(session: Session) -> ListGalleryOpportunities:
    return ListGalleryOpportunities(SqlGalleryOpportunityReader(session))


def build_create_gallery(session: Session):
    from app.adapters.outbound.media.gallery_events import EventGalleryContext
    from app.adapters.outbound.persistence.events.gallery_reader import SqlGalleryEventReader
    from app.adapters.outbound.persistence.articles.gallery_reader import SqlGalleryReportReader
    from app.adapters.outbound.persistence.users.reader import SqlUserReader
    from app.adapters.outbound.persistence.media.gallery_unit_of_work import SqlGalleryUnitOfWork
    from app.core.content.media.application.commands import CreateGallery

    events = EventGalleryContext(
        SqlGalleryEventReader(session), SqlGalleryReportReader(session, SqlUserReader(session)),
    )
    return CreateGallery(SqlGalleryUnitOfWork(session, events))


def build_get_caption(session: Session) -> GetCaption:
    return GetCaption(SqlMediaReader(session))


def build_update_caption(session: Session) -> UpdateCaption:
    return UpdateCaption(SqlMediaUnitOfWork(session))


def build_get_image(session: Session, *, media_directory: str | Path) -> GetImage:
    return GetImage(SqlMediaReader(session), LocalMediaStorage(media_directory))


def build_upload_image(
    session: Session, *, media_directory: str | Path,
    max_upload_bytes: int = 20 * 1024 * 1024,
) -> UploadImage:
    return UploadImage(
        SqlMediaUnitOfWork(session),
        PillowImageProcessor(max_file_size=max_upload_bytes),
        LocalMediaStorage(media_directory),
    )


def configured_media_directory(directory: str) -> Path:
    path = Path(directory)
    return path if path.is_absolute() else Path(__file__).resolve().parents[2] / path
