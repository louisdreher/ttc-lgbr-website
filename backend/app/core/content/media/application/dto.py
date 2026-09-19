from dataclasses import dataclass


@dataclass(frozen=True)
class UploadImageCommand:
    data: bytes
    original_filename: str
    uploaded_by_user_id: int


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
