from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field, ConfigDict, StrictBool


class GalleryOpportunityResponse(BaseModel):
    event_id: int
    title: str
    starts_at: datetime
    ends_at: datetime | None
    team_match_id: int | None


class GalleryOpportunityPageResponse(BaseModel):
    items: list[GalleryOpportunityResponse]
    total: int
    offset: int
    limit: int


class CreateGalleryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1)
    event_id: Annotated[int, Field(gt=0, strict=True)] | None = None
    gallery_date: date | None = None
    show_date: StrictBool | None = None
    media_ids: list[Annotated[int, Field(gt=0, strict=True)]] = Field(default_factory=list)


class CreatedGalleryResponse(BaseModel):
    id: int
    cover_image_id: int | None
    gallery_date: date
    show_date: bool


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
