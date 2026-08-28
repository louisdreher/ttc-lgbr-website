from datetime import datetime, timezone

import sqlalchemy as sa
from sqlmodel import Field, SQLModel

from app.domains.content.types import Visibility


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GalleryMedia(SQLModel, table=True):
    __tablename__ = "gallery_media"

    gallery_id: int = Field(
        foreign_key="gallery.id",
        ondelete="CASCADE",
        primary_key=True,
    )
    media_asset_id: int = Field(
        foreign_key="media_asset.id",
        ondelete="CASCADE",
        primary_key=True,
    )
    sort_order: int = Field(default=0)
    caption_override: str | None = None


class MediaAsset(SQLModel, table=True):
    __tablename__ = "media_asset"

    id: int | None = Field(default=None, primary_key=True)
    storage_key: str = Field(unique=True)
    original_filename: str
    mime_type: str
    file_size: int = Field(ge=0)
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    caption: str | None = None
    alt_text: str | None = None
    photographer: str | None = None
    uploaded_by_user_id: int = Field(
        foreign_key="user.id",
        index=True,
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_type=sa.DateTime(timezone=True),
    )


class Gallery(SQLModel, table=True):
    __tablename__ = "gallery"

    id: int | None = Field(default=None, primary_key=True)
    event_id: int | None = Field(
        default=None,
        foreign_key="event.id",
        ondelete="SET NULL",
        unique=True,
        index=True,
    )
    title: str
    slug: str | None = Field(default=None, unique=True, index=True)
    description: str | None = None
    visibility: Visibility = Field(
        default=Visibility.PUBLIC,
        sa_type=sa.Enum(Visibility, name="content_visibility"),
        index=True,
    )
    cover_image_id: int | None = Field(
        default=None,
        foreign_key="media_asset.id",
        ondelete="SET NULL",
    )
    created_by_user_id: int = Field(
        foreign_key="user.id",
        index=True,
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_type=sa.DateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_type=sa.DateTime(timezone=True),
    )
