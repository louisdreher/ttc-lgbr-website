from dataclasses import dataclass, replace
from datetime import date


class GalleryError(ValueError):
    """A gallery operation would violate its image or cover rules."""


@dataclass(frozen=True, kw_only=True)
class Gallery:
    """Ordered media references; operations return a new, validated gallery.

    File storage, access checks and event uniqueness belong to later use cases.
    """

    title: str
    gallery_date: date
    show_date: bool = True
    id: int | None = None
    event_id: int | None = None
    media_ids: tuple[int, ...] = ()
    cover_image_id: int | None = None

    def __post_init__(self) -> None:
        if type(self.gallery_date) is not date:
            raise GalleryError("Eine Galerie benötigt ein gültiges Galeriedatum.")
        if type(self.show_date) is not bool:
            raise GalleryError("Die Datumsanzeige muss ein Wahrheitswert sein.")
        title = self.title.strip()
        if not title:
            raise GalleryError("Eine Galerie benötigt einen Titel.")
        # Copy incoming collections so callers cannot mutate membership indirectly.
        media_ids = tuple(self.media_ids)
        if any(type(media_id) is not int or media_id <= 0 for media_id in media_ids):
            raise GalleryError("Medien-IDs müssen positive ganze Zahlen sein.")
        if len(set(media_ids)) != len(media_ids):
            raise GalleryError("Ein Bild darf nur einmal in einer Galerie vorkommen.")
        cover = self.cover_image_id
        if cover is not None and (type(cover) is not int or cover not in media_ids):
            raise GalleryError("Das Vorschaubild muss zur Galerie gehören.")
        if cover is None and media_ids:
            cover = media_ids[0]
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "media_ids", media_ids)
        object.__setattr__(self, "cover_image_id", cover)

    def add_image(self, media_id: int) -> "Gallery":
        if type(media_id) is not int or media_id <= 0:
            raise GalleryError("Medien-IDs müssen positive ganze Zahlen sein.")
        if media_id in self.media_ids:
            return self
        return replace(self, media_ids=(*self.media_ids, media_id))

    def remove_image(self, media_id: int) -> "Gallery":
        if media_id not in self.media_ids:
            return self
        remaining = tuple(item for item in self.media_ids if item != media_id)
        cover = None if self.cover_image_id == media_id else self.cover_image_id
        return replace(self, media_ids=remaining, cover_image_id=cover)

    def set_cover(self, media_id: int) -> "Gallery":
        return replace(self, cover_image_id=media_id)

    def reorder_images(self, media_ids: tuple[int, ...]) -> "Gallery":
        ordered = tuple(media_ids)
        if len(ordered) != len(self.media_ids) or set(ordered) != set(self.media_ids):
            raise GalleryError("Die Reihenfolge muss jedes vorhandene Bild genau einmal enthalten.")
        return replace(self, media_ids=ordered)
