import logging

from app.core.content.media.application.dto import UploadImageCommand, UploadedImage
from app.core.content.media.application.ports import (
    ImageProcessor,
    MediaStorage,
    MediaUnitOfWork,
)
from app.core.content.media.domain.asset import MediaAsset

logger = logging.getLogger(__name__)


class UploadImage:
    def __init__(
        self, uow: MediaUnitOfWork, processor: ImageProcessor, storage: MediaStorage
    ) -> None:
        self.uow = uow
        self.processor = processor
        self.storage = storage

    def execute(self, command: UploadImageCommand) -> UploadedImage:
        # Identity and authorization must come from the trusted inbound adapter.
        if not command.original_filename.strip() or command.uploaded_by_user_id <= 0:
            raise ValueError("Filename and a positive uploader ID are required.")
        image = self.processor.process(command.data)
        key = self.storage.save(image)
        committed = False
        try:
            with self.uow:
                asset = self.uow.media.save(MediaAsset(
                    storage_key=key,
                    original_filename=command.original_filename,
                    mime_type=image.mime_type,
                    file_size=image.file_size,
                    width=image.width,
                    height=image.height,
                    uploaded_by_user_id=command.uploaded_by_user_id,
                ))
                if asset.id is None:
                    raise RuntimeError("Saved media asset has no ID.")
                result = UploadedImage(
                    id=asset.id,
                    mime_type=asset.mime_type,
                    file_size=asset.file_size,
                    width=asset.width,
                    height=asset.height,
                )
                self.uow.commit()
                committed = True
            return result
        except Exception as error:
            if not committed:
                try:
                    self.storage.delete(key)
                except Exception:
                    logger.exception("Could not clean up media file %s", key)
                    error.add_note(f"Media cleanup failed for storage key {key}.")
            raise
