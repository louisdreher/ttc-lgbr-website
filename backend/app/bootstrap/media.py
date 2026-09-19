from pathlib import Path

from sqlmodel import Session

from app.adapters.outbound.media.image_processor import PillowImageProcessor
from app.adapters.outbound.media.local_storage import LocalMediaStorage
from app.adapters.outbound.persistence.media.unit_of_work import SqlMediaUnitOfWork
from app.core.content.media.application.commands import UploadImage


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
