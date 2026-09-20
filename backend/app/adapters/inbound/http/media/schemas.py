from pydantic import BaseModel, Field, ConfigDict


class CaptionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    caption: str | None = Field(max_length=1000)


class CaptionResponse(BaseModel):
    caption: str | None


class UploadedImageResponse(BaseModel):
    id: int
    mime_type: str
    file_size: int
    width: int
    height: int
