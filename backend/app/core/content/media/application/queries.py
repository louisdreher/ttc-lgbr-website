from app.core.content.media.application.dto import GetImageQuery
from app.core.content.media.application.errors import ImageNotFound
from app.core.content.media.application.ports import MediaReader, MediaStorage


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
