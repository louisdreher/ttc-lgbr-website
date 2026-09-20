from datetime import date
from dataclasses import replace
from unittest.mock import Mock

import pytest

from app.core.content.media.application.commands import CreateGallery
from app.core.content.media.application.dto import CreateGalleryCommand, GalleryEventContext
from app.core.content.media.application.errors import (
    EventGalleryAlreadyExists, GalleryAccessDenied, ImageNotFound,
)
from app.core.content.media.domain.asset import MediaAsset
from app.core.content.media.domain.gallery import GalleryError


class FakeUnitOfWork:
    def __init__(self):
        self.galleries = Mock()
        self.galleries.exists_for_event.return_value = False
        self.galleries.save.side_effect = lambda gallery, **kwargs: replace(gallery, id=10)
        self.events = Mock()
        self.events.for_creation.return_value = GalleryEventContext(True, 42)
        self.media = Mock()
        self.media.get.side_effect = lambda media_id: MediaAsset(
            storage_key=f"{media_id}.webp", original_filename="test.jpg",
            mime_type="image/webp", file_size=10, width=10, height=10,
            uploaded_by_user_id=1, id=media_id,
        )
        self.committed = False
        self.exited = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.exited = True

    def commit(self):
        self.committed = True


def command(**changes):
    return CreateGalleryCommand(**dict(
        title="Turnier", gallery_date=date(2026, 9, 20), user_id=1, can_upload=True, event_id=7, media_ids=(11, 12)
    ) | changes)


@pytest.mark.parametrize("images, expected", [((11, 12), (11, 12, 42)), ((42, 11), (42, 11)), ((), (42,))])
def test_event_gallery_includes_report_cover_once(images, expected):
    uow = FakeUnitOfWork()
    result = CreateGallery(uow).execute(command(media_ids=images))
    gallery = uow.galleries.save.call_args.args[0]
    assert gallery.media_ids == expected
    assert gallery.cover_image_id == result.cover_image_id == 42
    assert result.id == 10
    assert uow.galleries.save.call_args.kwargs == {"created_by_user_id": 1}
    assert uow.committed and uow.exited


def test_without_report_cover_first_selected_image_becomes_cover():
    uow = FakeUnitOfWork()
    uow.events.for_creation.return_value = GalleryEventContext(True)
    assert CreateGallery(uow).execute(command()).cover_image_id == 11


def test_editor_can_create_empty_standalone_gallery():
    uow = FakeUnitOfWork()
    result = CreateGallery(uow).execute(command(event_id=None, can_manage_media=True, media_ids=()))
    assert result.cover_image_id is None
    uow.events.for_creation.assert_not_called()


@pytest.mark.parametrize("changes", [{"can_upload": False}, {"event_id": None}, {"user_id": 0}])
def test_unauthorized_creation_never_saves(changes):
    uow = FakeUnitOfWork()
    with pytest.raises(GalleryAccessDenied):
        CreateGallery(uow).execute(command(**changes))
    uow.galleries.save.assert_not_called()
    assert not uow.committed


@pytest.mark.parametrize("context", [None, GalleryEventContext(False)])
def test_missing_event_or_uneditable_report_is_rejected(context):
    uow = FakeUnitOfWork()
    uow.events.for_creation.return_value = context
    with pytest.raises(GalleryAccessDenied):
        CreateGallery(uow).execute(command())
    assert not uow.committed


def test_existing_event_gallery_is_rejected():
    uow = FakeUnitOfWork()
    uow.galleries.exists_for_event.return_value = True
    with pytest.raises(EventGalleryAlreadyExists):
        CreateGallery(uow).execute(command())
    uow.galleries.save.assert_not_called()


@pytest.mark.parametrize("image", [None, MediaAsset(
    storage_key="foreign.webp", original_filename="x", mime_type="image/webp",
    file_size=10, width=10, height=10, uploaded_by_user_id=99,
)])
def test_missing_or_foreign_selected_image_is_rejected(image):
    uow = FakeUnitOfWork()
    uow.media.get.side_effect = None
    uow.media.get.return_value = image
    with pytest.raises(ImageNotFound):
        CreateGallery(uow).execute(command())
    uow.galleries.save.assert_not_called()
    assert not uow.committed


def test_repository_failure_does_not_commit():
    uow = FakeUnitOfWork()
    uow.galleries.save.side_effect = RuntimeError("database failed")
    with pytest.raises(RuntimeError):
        CreateGallery(uow).execute(command())
    assert not uow.committed
    assert uow.exited


def test_existing_foreign_report_cover_can_be_adopted_by_report_writer():
    uow = FakeUnitOfWork()
    original_lookup = uow.media.get.side_effect
    uow.media.get.side_effect = lambda media_id: replace(
        original_lookup(media_id), uploaded_by_user_id=99 if media_id == 42 else 1
    )
    assert CreateGallery(uow).execute(command()).cover_image_id == 42
    assert uow.committed


def test_missing_report_cover_prevents_creation():
    uow = FakeUnitOfWork()
    original_lookup = uow.media.get.side_effect
    uow.media.get.side_effect = lambda media_id: (
        None if media_id == 42 else original_lookup(media_id)
    )
    with pytest.raises(ImageNotFound):
        CreateGallery(uow).execute(command())
    uow.galleries.save.assert_not_called()
    assert not uow.committed


def test_uses_event_date_when_no_explicit_date_is_given():
    uow = FakeUnitOfWork()
    uow.events.for_creation.return_value = GalleryEventContext(True, 42, date(2007, 6, 16))
    result = CreateGallery(uow).execute(command(gallery_date=None, show_date=False))
    assert result.gallery_date == date(2007, 6, 16)
    assert result.show_date is False
    assert uow.galleries.save.call_args.args[0].gallery_date == date(2007, 6, 16)


def test_explicit_date_overrides_event_suggestion():
    uow = FakeUnitOfWork()
    uow.events.for_creation.return_value = GalleryEventContext(True, 42, date(2007, 6, 16))
    result = CreateGallery(uow).execute(command(gallery_date=date(2007, 6, 17)))
    assert result.gallery_date == date(2007, 6, 17)


def test_standalone_gallery_requires_explicit_date():
    uow = FakeUnitOfWork()
    with pytest.raises(GalleryError, match="Galeriedatum"):
        CreateGallery(uow).execute(command(event_id=None, can_manage_media=True, gallery_date=None))
    uow.galleries.save.assert_not_called()
    assert not uow.committed


@pytest.mark.parametrize("event_id, choice, expected", [
    (7, None, True), (None, None, False),
    (7, False, False), (None, True, True),
])
def test_date_display_defaults_and_explicit_choices(event_id, choice, expected):
    uow = FakeUnitOfWork()
    result = CreateGallery(uow).execute(command(
        event_id=event_id, can_manage_media=True, show_date=choice,
    ))
    assert result.show_date is expected
    assert uow.galleries.save.call_args.args[0].show_date is expected
