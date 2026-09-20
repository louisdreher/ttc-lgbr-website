from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, kw_only=True)
class CreateGalleryCommand:
    title: str
    user_id: int
    can_upload: bool
    can_manage_media: bool = False
    event_id: int | None = None
    media_ids: tuple[int, ...] = ()
    gallery_date: date | None = None
    show_date: bool | None = None


@dataclass(frozen=True)
class GalleryEventContext:
    can_edit_report: bool
    report_cover_image_id: int | None = None
    event_date: date | None = None


@dataclass(frozen=True)
class CreatedGallery:
    id: int
    cover_image_id: int | None
    gallery_date: date
    show_date: bool


@dataclass(frozen=True)
class ImageReference:
    storage_key: str
    uploaded_by_user_id: int
    caption: str | None = None


@dataclass(frozen=True)
class GetImageQuery:
    media_id: int
    user_id: int
    can_manage_media: bool = False


@dataclass(frozen=True)
class UploadImageCommand:
    data: bytes
    original_filename: str
    uploaded_by_user_id: int
    caption: str | None = None


@dataclass(frozen=True)
class UpdateCaptionCommand:
    media_id: int
    user_id: int
    caption: str | None
    can_manage_media: bool = False


@dataclass(frozen=True)
class UploadedImage:
    id: int
    mime_type: str
    file_size: int
    width: int
    height: int


@dataclass(frozen=True)
class ProcessedImage:
    data: bytes
    width: int
    height: int
    mime_type: str

    @property
    def file_size(self) -> int:
        return len(self.data)
