from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field, ConfigDict, StrictBool, AwareDatetime


class GalleryNewEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=255)
    starts_at: AwareDatetime
    category_id: int = Field(gt=0, strict=True)
    ends_at: AwareDatetime | None = None
    location: str | None = None
    description: str | None = None


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
    new_event: GalleryNewEventRequest | None = None


class CreatedGalleryResponse(BaseModel):
    id: int
    cover_image_id: int | None
    gallery_date: date
    show_date: bool


class GallerySummaryResponse(CreatedGalleryResponse):
    title: str
    event_id: int | None
    image_count: int


class GalleryDetailsResponse(GallerySummaryResponse):
    media_ids: list[int]
    updated_at: datetime
    created_by_user_id: int


class GalleryPageResponse(BaseModel):
    items: list[GallerySummaryResponse]
    total: int
    offset: int
    limit: int
    years: list[int]


class UpdateGalleryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1)
    gallery_date: date
    show_date: StrictBool
    media_ids: list[Annotated[int, Field(gt=0, strict=True)]]
    cover_image_id: Annotated[int, Field(gt=0, strict=True)] | None
    updated_at: AwareDatetime


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


class GalleryImageCaptionResponse(BaseModel):
    caption: str | None
    can_edit: bool
