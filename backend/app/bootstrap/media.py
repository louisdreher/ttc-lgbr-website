from pathlib import Path

from sqlmodel import Session

from app.adapters.outbound.media.image_processor import PillowImageProcessor
from app.adapters.outbound.media.local_storage import LocalMediaStorage
from app.adapters.outbound.persistence.media.unit_of_work import SqlMediaUnitOfWork
from app.core.content.media.application.commands import UploadImage


def build_upload_image(session: Session, *, media_directory: str | Path) -> UploadImage:
    return UploadImage(
        SqlMediaUnitOfWork(session),
        PillowImageProcessor(),
        LocalMediaStorage(media_directory),
    )
