import re
from pathlib import Path
from uuid import uuid4

from app.core.content.media.application.dto import ProcessedImage
from app.core.content.media.application.errors import (
    InvalidImage,
    ImageNotFound,
    InvalidStorageKey,
    MediaStorageError,
)


class LocalMediaStorage:
    """Store processed images below a constructor-configured, private directory."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory).resolve()

    def _path(self, storage_key: str) -> Path:
        if not re.fullmatch(r"images/[0-9a-f]{32}\.webp", storage_key):
            raise InvalidStorageKey("Invalid media storage key.")
        path = self.directory / storage_key
        if path.is_symlink() or not path.resolve().is_relative_to(self.directory):
            raise InvalidStorageKey("Media path escapes the storage directory.")
        return path

    def save(self, image: ProcessedImage) -> str:
        # Image decoding belongs to ImageProcessor; accept its WebP result only.
        if image.mime_type != "image/webp" or not image.data:
            raise InvalidImage("Storage expects a non-empty processed WebP image.")
        storage_key = f"images/{uuid4().hex}.webp"
        try:
            path = self._path(storage_key)
            path.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation protects existing files even on a UUID collision.
            created = False
            try:
                with path.open("xb") as output:
                    created = True
                    output.write(image.data)
            except OSError:
                # The context manager closes the handle before Windows unlinks it.
                if created:
                    path.unlink(missing_ok=True)
                raise
        except OSError as exc:
            raise MediaStorageError("Could not save media image.") from exc
        return storage_key

    def delete(self, storage_key: str) -> None:
        try:
            self._path(storage_key).unlink(missing_ok=True)
        except OSError as exc:
            raise MediaStorageError("Could not delete media image.") from exc

    def read(self, storage_key: str) -> bytes:
        try:
            return self._path(storage_key).read_bytes()
        except FileNotFoundError as exc:
            raise ImageNotFound() from exc
        except OSError as exc:
            raise MediaStorageError("Could not read media image.") from exc
