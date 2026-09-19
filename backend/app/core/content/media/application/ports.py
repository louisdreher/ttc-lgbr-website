from typing import Protocol

from app.core.content.media.application.dto import ProcessedImage


class ImageProcessor(Protocol):
    def process(self, data: bytes) -> ProcessedImage:
        """Create a metadata-free master image, or raise InvalidImage."""
        ...
