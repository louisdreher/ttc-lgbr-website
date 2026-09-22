import logging
from dataclasses import replace
from datetime import timezone
from app.core.content.media.application.dto import UpdateGalleryCommand
from app.core.content.media.application.errors import GalleryNotFound, GalleryConflict
from app.core.content.media.application.queries import require_gallery_access

from app.core.content.media.application.dto import (
    CreateGalleryCommand,
    CreatedGallery,
    UpdateCaptionCommand,
    UploadedImage,
    UploadImageCommand,
)
from app.core.content.media.application.errors import (
    EventGalleryAlreadyExists,
    GalleryAccessDenied,
    ImageNotFound,
)
from app.core.content.media.application.ports import (
    GalleryUnitOfWork,
    ImageProcessor,
    MediaStorage,
    MediaUnitOfWork,
)
from app.core.content.media.domain.asset import MediaAsset, normalize_caption
from app.core.content.media.domain.gallery import Gallery, GalleryError

logger = logging.getLogger(__name__)


class UpdateGallery:
    def __init__(self, uow: GalleryUnitOfWork):
        self.uow = uow

    def execute(self, command: UpdateGalleryCommand) -> int:
        require_gallery_access(command)
        with self.uow:
            current = self.uow.galleries.get_for_update(command.gallery_id)
            if current is None or (not command.can_manage_media and current.created_by_user_id != command.user_id):
                raise GalleryNotFound()
            # SQLite timestamps are naive; PostgreSQL returns aware UTC values.
            stamp = current.updated_at
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            if command.updated_at != stamp:
                raise GalleryConflict("Die Galerie wurde inzwischen geändert. Bitte neu laden.")
            gallery = replace(current.gallery, title=command.title,
                gallery_date=command.gallery_date, show_date=command.show_date,
                media_ids=command.media_ids, cover_image_id=command.cover_image_id)
            for media_id in set(gallery.media_ids) - set(current.gallery.media_ids):
                image = self.uow.media.get(media_id)
                if image is None or (not command.can_manage_media and image.uploaded_by_user_id != command.user_id):
                    raise ImageNotFound()
            self.uow.galleries.update(gallery)
            self.uow.commit()
            return command.gallery_id


class CreateGallery:
    def __init__(self, uow: GalleryUnitOfWork) -> None:
        self.uow = uow

    def execute(self, command: CreateGalleryCommand) -> CreatedGallery:
        if command.user_id <= 0 or not command.can_upload:
            raise GalleryAccessDenied("Keine Berechtigung zum Anlegen einer Galerie.")
        with self.uow:
            event_id = command.event_id
            if command.new_event is not None:
                if event_id is not None:
                    raise GalleryError("Bitte entweder ein bestehendes oder ein neues Event wählen.")
                if not command.can_manage_media:
                    raise GalleryAccessDenied("Neue Events mit Galerie erfordern Redaktionsrechte.")
                event_id = self.uow.events.create_hidden(command.new_event, command.user_id)
            cover = None
            gallery_date = command.gallery_date
            if event_id is not None:
                if event_id <= 0:
                    raise GalleryError("Ungültige Event-ID.")
                context = self.uow.events.for_creation(event_id, command.user_id)
                if context is None or not (command.can_manage_media or context.can_edit_report):
                    raise GalleryAccessDenied("Event nicht verfügbar oder nicht bearbeitbar.")
                if self.uow.galleries.exists_for_event(event_id):
                    raise EventGalleryAlreadyExists("Für dieses Event existiert bereits eine Galerie.")
                cover = context.report_cover_image_id
                if gallery_date is None:
                    gallery_date = context.event_date
            elif not command.can_manage_media:
                raise GalleryAccessDenied("Galerien ohne Event erfordern Redaktionsrechte.")

            if gallery_date is None:
                raise GalleryError("Bitte ein Galeriedatum angeben.")
            gallery = Gallery(
                title=command.title, event_id=event_id, media_ids=command.media_ids,
                gallery_date=gallery_date,
                show_date=(
                    event_id is not None
                    if command.show_date is None else command.show_date
                ),
            )
            if cover is not None:
                gallery = gallery.add_image(cover).set_cover(cover)
            for media_id in gallery.media_ids:
                image = self.uow.media.get(media_id)
                # The report's existing cover is authorized through report access;
                # newly selected images must be owned by the actor or an editor.
                if image is None or (
                    media_id != cover
                    and not command.can_manage_media
                    and image.uploaded_by_user_id != command.user_id
                ):
                    raise ImageNotFound()
            saved = self.uow.galleries.save(gallery, created_by_user_id=command.user_id)
            if saved.id is None:
                raise RuntimeError("Gespeicherte Galerie besitzt keine ID.")
            result = CreatedGallery(saved.id, saved.cover_image_id, saved.gallery_date, saved.show_date)
            self.uow.commit()
            return result


class UploadImage:
    def __init__(
        self, uow: MediaUnitOfWork, processor: ImageProcessor, storage: MediaStorage
    ) -> None:
        self.uow = uow
        self.processor = processor
        self.storage = storage

    def execute(self, command: UploadImageCommand) -> UploadedImage:
        # Identity and authorization must come from the trusted inbound adapter.
        if not command.original_filename.strip() or command.uploaded_by_user_id <= 0:
            raise ValueError("Filename and a positive uploader ID are required.")
        caption = normalize_caption(command.caption)
        image = self.processor.process(command.data)
        key = self.storage.save(image)
        committed = False
        try:
            with self.uow:
                asset = self.uow.media.save(
                    MediaAsset(
                        storage_key=key,
                        original_filename=command.original_filename,
                        mime_type=image.mime_type,
                        file_size=image.file_size,
                        width=image.width,
                        height=image.height,
                        uploaded_by_user_id=command.uploaded_by_user_id,
                        caption=caption,
                    )
                )
                if asset.id is None:
                    raise RuntimeError("Saved media asset has no ID.")
                result = UploadedImage(
                    id=asset.id,
                    mime_type=asset.mime_type,
                    file_size=asset.file_size,
                    width=asset.width,
                    height=asset.height,
                )
                self.uow.commit()
                committed = True
            return result
        except Exception as error:
            if not committed:
                try:
                    self.storage.delete(key)
                except Exception:
                    logger.exception("Could not clean up media file %s", key)
                    error.add_note(f"Media cleanup failed for storage key {key}.")
            raise


class UpdateCaption:
    def __init__(self, uow: MediaUnitOfWork) -> None:
        self.uow = uow

    def execute(self, command: UpdateCaptionCommand) -> str | None:
        with self.uow:
            asset = self.uow.media.get(command.media_id)
            if asset is None or (
                asset.uploaded_by_user_id != command.user_id and not command.can_manage_media
            ):
                raise ImageNotFound()
            asset = asset.with_caption(command.caption)
            self.uow.media.update_caption(asset)
            self.uow.commit()
            return asset.caption
