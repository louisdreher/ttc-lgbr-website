from __future__ import annotations

from typing import Protocol, Self

from app.core.content.media.application.dto import ImageReference, ProcessedImage
from app.core.content.media.domain.asset import MediaAsset
from app.core.content.media.domain.gallery import Gallery
from app.core.content.media.application.dto import GalleryEventContext
from app.core.content.media.application.dto import GalleryNewEvent
from app.core.content.media.application.dto import GalleryOpportunitiesQuery, GalleryOpportunityPage
from app.core.content.media.application.dto import GallerySnapshot, GalleryDetails, GalleryPage, ListGalleriesQuery


class GalleryReader(Protocol):
    def find_by_event(self, event_id: int) -> GalleryDetails | None: ...
    def list(self, query: ListGalleriesQuery) -> GalleryPage: ...
    def get(self, gallery_id: int) -> GalleryDetails | None: ...


class GalleryOpportunityReader(Protocol):
    def opportunities(self, query: GalleryOpportunitiesQuery) -> GalleryOpportunityPage: ...


class GalleryRepository(Protocol):
    def get_for_update(self, gallery_id: int) -> GallerySnapshot | None: ...
    def update(self, gallery: Gallery) -> None: ...
    def exists_for_event(self, event_id: int) -> bool: ...
    def save(self, gallery: Gallery, *, created_by_user_id: int) -> Gallery:
        """Insert without committing; enforce one gallery per event in persistence."""
        ...


class GalleryEvents(Protocol):
    def create_hidden(self, values: GalleryNewEvent, user_id: int) -> int:
        """Create in the same transaction without committing."""
        ...

    def for_creation(self, event_id: int, user_id: int) -> GalleryEventContext | None:
        """Read event/report through public contracts in the creation transaction.

        None means the event is missing. The adapter must coordinate concurrent
        gallery creation and report-cover changes before returning this context.
        """
        ...


class GalleryUnitOfWork(Protocol):
    galleries: GalleryRepository
    media: MediaRepository
    events: GalleryEvents

    def __enter__(self) -> Self: ...
    def __exit__(self, exc_type, exc_value, traceback) -> None: ...
    def commit(self) -> None: ...


class MediaRepository(Protocol):
    def get(self, media_id: int) -> MediaAsset | None: ...
    def update_caption(self, asset: MediaAsset) -> None: ...

    def save(self, asset: MediaAsset) -> MediaAsset:
        """Insert a new asset and return its assigned ID; do not commit."""
        ...


class MediaUnitOfWork(Protocol):
    media: MediaRepository

    def __enter__(self) -> Self: ...
    def __exit__(self, exc_type, exc_value, traceback) -> None: ...
    def commit(self) -> None: ...


class ImageProcessor(Protocol):
    def process(self, data: bytes) -> ProcessedImage:
        """Create a metadata-free master image, or raise InvalidImage."""
        ...


class MediaStorage(Protocol):
    def read(self, storage_key: str) -> bytes:
        """Read image bytes; raise ImageNotFound or MediaStorageError on failure."""
        ...

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


class MediaReader(Protocol):
    def get_image(self, media_id: int) -> ImageReference | None: ...
