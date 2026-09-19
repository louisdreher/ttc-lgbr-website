from dataclasses import dataclass


@dataclass(frozen=True)
class MediaAsset:
    storage_key: str
    original_filename: str
    mime_type: str
    file_size: int
    width: int
    height: int
    uploaded_by_user_id: int
    id: int | None = None
