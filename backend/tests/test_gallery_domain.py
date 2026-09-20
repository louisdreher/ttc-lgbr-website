from datetime import date
from dataclasses import FrozenInstanceError

import pytest

from app.core.content.media.domain.gallery import Gallery, GalleryError


def test_empty_gallery_has_no_cover_and_optional_event():
    gallery = Gallery(gallery_date=date(2026, 9, 20), title="  Kreismeisterschaften  ")
    assert gallery.title == "Kreismeisterschaften"
    assert gallery.event_id is None
    assert gallery.media_ids == ()
    assert gallery.cover_image_id is None


def test_add_preserves_order_and_uses_first_image_as_cover():
    original = Gallery(gallery_date=date(2026, 9, 20), title="Turnier", event_id=7)
    gallery = original.add_image(42).add_image(17)
    assert original.media_ids == ()
    assert gallery.media_ids == (42, 17)
    assert gallery.cover_image_id == 42
    assert gallery.event_id == 7
    assert gallery.add_image(42) == gallery


def test_reorder_preserves_selected_cover():
    gallery = Gallery(gallery_date=date(2026, 9, 20), title="Turnier", media_ids=(1, 2, 3)).set_cover(2)
    reordered = gallery.reorder_images((3, 1, 2))
    assert reordered.media_ids == (3, 1, 2)
    assert reordered.cover_image_id == 2
    assert gallery.media_ids == (1, 2, 3)


def test_removing_cover_chooses_first_remaining_in_current_order():
    gallery = Gallery(gallery_date=date(2026, 9, 20), title="Turnier", media_ids=(3, 1, 2), cover_image_id=1)
    updated = gallery.remove_image(1)
    assert updated.media_ids == (3, 2)
    assert updated.cover_image_id == 3
    assert updated.remove_image(2).cover_image_id == 3
    empty = updated.remove_image(3).remove_image(2)
    assert empty.media_ids == ()
    assert empty.cover_image_id is None
    assert empty.remove_image(99) == empty


@pytest.mark.parametrize("order", [(1, 2), (1, 2, 3, 4), (1, 1, 2), (1, 2, 9)])
def test_reorder_rejects_missing_duplicate_or_unknown_images(order):
    gallery = Gallery(gallery_date=date(2026, 9, 20), title="Turnier", media_ids=(1, 2, 3))
    with pytest.raises(GalleryError):
        gallery.reorder_images(order)
    assert gallery.media_ids == (1, 2, 3)


def test_unknown_cover_is_rejected_without_adding_it():
    gallery = Gallery(gallery_date=date(2026, 9, 20), title="Turnier", media_ids=(1, 2))
    with pytest.raises(GalleryError):
        gallery.set_cover(99)
    assert gallery.media_ids == (1, 2)
    assert gallery.cover_image_id == 1


@pytest.mark.parametrize("values", [
    {"title": " "},
    {"media_ids": (1, 1)},
    {"media_ids": (1,), "cover_image_id": 2},
    {"cover_image_id": 1},
    {"media_ids": (0,)},
])
def test_invalid_initial_state_is_rejected(values):
    with pytest.raises(GalleryError):
        Gallery(gallery_date=date(2026, 9, 20), **({"title": "Turnier"} | values))


@pytest.mark.parametrize("media_id", [0, -1, True, 1.5])
def test_invalid_new_media_ids_are_rejected(media_id):
    with pytest.raises(GalleryError):
        Gallery(gallery_date=date(2026, 9, 20), title="Turnier").add_image(media_id)


def test_membership_cannot_be_changed_by_mutating_the_input():
    images = [1, 2]
    gallery = Gallery(gallery_date=date(2026, 9, 20), title="Turnier", media_ids=images)
    images.append(3)
    assert gallery.media_ids == (1, 2)
    with pytest.raises(FrozenInstanceError):
        gallery.cover_image_id = 99


@pytest.mark.parametrize("value", [None, "2026-09-20", 2026])
def test_requires_a_date(value):
    with pytest.raises(GalleryError, match="Galeriedatum"):
        Gallery(title="Turnier", gallery_date=value)


def test_image_operations_preserve_date_and_display_preference():
    gallery = Gallery(title="Archiv", gallery_date=date(2007, 6, 16), show_date=False)
    updated = gallery.add_image(1).add_image(2).reorder_images((2, 1)).set_cover(2).remove_image(1)
    assert updated.gallery_date == gallery.gallery_date
    assert updated.show_date is False
