from pydantic import BaseModel


class UploadedImageResponse(BaseModel):
    id: int
    mime_type: str
    file_size: int
    width: int
    height: int
