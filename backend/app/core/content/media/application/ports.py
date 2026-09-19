from typing import Protocol

from app.core.content.media.application.dto import ProcessedImage


class ImageProcessor(Protocol):
    def process(self, data: bytes) -> ProcessedImage:
        """Create a metadata-free master image, or raise InvalidImage."""
        ...


class MediaStorage(Protocol):
    def save(self, image: ProcessedImage) -> str:
        """Store a processed WebP image and return an opaque relative key.

        Raise MediaStorageError on storage failure; never overwrite an asset.
        """
        ...

    def delete(self, storage_key: str) -> None:
        """Remove a stored image; a missing file is already deleted.

        Raise InvalidStorageKey for invalid keys, MediaStorageError on I/O failure.
        """
        ...
