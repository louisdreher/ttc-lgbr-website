from app.core.content.media.application.dto import GetImageQuery, ImageReference
from app.core.content.media.application.errors import ImageNotFound
from app.core.content.media.application.ports import MediaReader, MediaStorage
from app.core.content.media.application.dto import GalleryOpportunitiesQuery, GalleryOpportunityPage
from app.core.content.media.application.ports import GalleryOpportunityReader
from app.core.content.media.application.errors import GalleryAccessDenied
from app.core.content.media.domain.gallery import GalleryError
from app.core.content.media.application.dto import GalleryAccess, GetGalleryQuery, ListGalleriesQuery
from app.core.content.media.application.errors import GalleryNotFound
from app.core.content.media.application.ports import GalleryReader
from app.core.content.media.application.ports import GalleryEvents
from app.core.content.media.application.dto import GetEventGalleryQuery, GalleryDetails, GalleryImageCaption


class GetEventGallery:
    """Read a gallery for report editing, without granting gallery management rights."""

    def __init__(self, reader: GalleryReader, events: GalleryEvents):
        self.reader, self.events = reader, events

    def execute(self, query: GetEventGalleryQuery) -> GalleryDetails | None:
        require_gallery_access(query)
        context = self.events.for_creation(query.event_id, query.user_id)
        if context is None:
            raise GalleryNotFound()
        if not query.can_manage_media and not context.can_edit_report:
            raise GalleryAccessDenied("Für die Galerieauswahl benötigst du einen bearbeitbaren Bericht.")
        return self.reader.find_by_event(query.event_id)


class GetEventGalleryImage:
    def __init__(self, galleries: GetEventGallery, media: MediaReader, storage: MediaStorage):
        self.galleries, self.media, self.storage = galleries, media, storage

    def _image(self, query: GetEventGalleryQuery, media_id: int) -> ImageReference:
        gallery = self.galleries.execute(query)
        if gallery is None or media_id not in gallery.media_ids:
            raise ImageNotFound()
        image = self.media.get_image(media_id)
        if image is None:
            raise ImageNotFound()
        return image

    def execute(self, query: GetEventGalleryQuery, media_id: int) -> bytes:
        return self.storage.read(self._image(query, media_id).storage_key)

    def caption(self, query: GetEventGalleryQuery, media_id: int) -> GalleryImageCaption:
        image = self._image(query, media_id)
        return GalleryImageCaption(image.caption, query.can_manage_media or image.uploaded_by_user_id == query.user_id)


def require_gallery_access(access: GalleryAccess) -> None:
    if not access.can_upload or access.user_id <= 0:
        raise GalleryAccessDenied("Keine Berechtigung zur Galerieverwaltung.")


class ListGalleries:
    def __init__(self, reader: GalleryReader):
        self.reader = reader

    def execute(self, query: ListGalleriesQuery):
        require_gallery_access(query)
        if query.offset < 0 or not 1 <= query.limit <= 100 or (query.year is not None and not 1 <= query.year <= 9999):
            raise GalleryError("Ungültige Filter oder Seitenauswahl.")
        return self.reader.list(query)


class GetGallery:
    def __init__(self, reader: GalleryReader):
        self.reader = reader

    def execute(self, query: GetGalleryQuery):
        require_gallery_access(query)
        gallery = self.reader.get(query.gallery_id)
        if gallery is None or (not query.can_manage_media and gallery.created_by_user_id != query.user_id):
            raise GalleryNotFound()
        return gallery


class GetGalleryImage:
    def __init__(self, galleries: GetGallery, media: MediaReader, storage: MediaStorage):
        self.galleries, self.media, self.storage = galleries, media, storage

    def execute(self, query: GetGalleryQuery, media_id: int) -> bytes:
        gallery = self.galleries.execute(query)
        if media_id not in gallery.media_ids:
            raise ImageNotFound()
        image = self.media.get_image(media_id)
        if image is None:
            raise ImageNotFound()
        return self.storage.read(image.storage_key)


class ListGalleryOpportunities:
    def __init__(self, reader: GalleryOpportunityReader):
        self.reader = reader

    def execute(self, query: GalleryOpportunitiesQuery) -> GalleryOpportunityPage:
        if query.user_id <= 0 or not query.can_upload:
            raise GalleryAccessDenied("Keine Berechtigung zur Galerieauswahl.")
        if query.group not in ("other_events", "team_matches"):
            raise GalleryError("Ungültige Eventgruppe.")
        if query.offset < 0 or not 1 <= query.limit <= 100:
            raise GalleryError("Ungültige Seitenauswahl.")
        return self.reader.opportunities(query)


class GetImage:
    def __init__(self, reader: MediaReader, storage: MediaStorage) -> None:
        self.reader = reader
        self.storage = storage

    def execute(self, query: GetImageQuery) -> bytes:
        image = self.reader.get_image(query.media_id)
        if image is None or (
            image.uploaded_by_user_id != query.user_id and not query.can_manage_media
        ):
            # Do not reveal another user's private upload through different errors.
            raise ImageNotFound()
        return self.storage.read(image.storage_key)


class GetCaption:
    def __init__(self, reader: MediaReader) -> None:
        self.reader = reader

    def execute(self, query: GetImageQuery) -> str | None:
        image = self.reader.get_image(query.media_id)
        if image is None or (
            image.uploaded_by_user_id != query.user_id and not query.can_manage_media
        ):
            raise ImageNotFound()
        return image.caption
