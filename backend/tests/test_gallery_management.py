from dataclasses import replace
from datetime import date
from unittest.mock import Mock, patch

import pytest
from sqlmodel import Session, select
from test_gallery_repository import engine  # noqa: F401
from app.bootstrap.media import build_create_gallery, build_get_gallery, build_list_galleries, build_update_gallery
from app.adapters.outbound.persistence.media.models import GalleryMedia, MediaAsset
from app.adapters.outbound.persistence.users.models import User
from app.core.content.media.application.dto import CreateGalleryCommand, GetGalleryQuery, ListGalleriesQuery, UpdateGalleryCommand, ImageReference
from app.core.content.media.application.errors import GalleryNotFound, GalleryConflict, ImageNotFound
from app.core.content.media.application.queries import GetGalleryImage
from app.core.content.media.domain.gallery import GalleryError


def create(session, **changes):
    args = dict(title="Galerie", gallery_date=date(2007, 6, 16), user_id=1,
                can_upload=True, can_manage_media=True, media_ids=(11, 42))
    return build_create_gallery(session).execute(CreateGalleryCommand(**(args | changes))).id


def access(gallery_id, **changes):
    return GetGalleryQuery(**(dict(gallery_id=gallery_id, user_id=1, can_upload=True) | changes))


def update(details, **changes):
    args = dict(gallery_id=details.id, user_id=1, can_upload=True, title=details.title,
                gallery_date=details.gallery_date, show_date=details.show_date,
                media_ids=details.media_ids, cover_image_id=details.cover_image_id, updated_at=details.updated_at)
    return UpdateGalleryCommand(**(args | changes))


def test_list_years_counts_pagination_and_ownership(engine):
    with Session(engine) as session:
        session.add(User(id=2, email="second@example.test", name="Other", password_hash="test"))
        session.commit()
        first = create(session)
        second = create(session, gallery_date=date(2026, 9, 20), media_ids=())
        create(session, gallery_date=date(1999, 1, 1), user_id=2, media_ids=())
        use_case = build_list_galleries(session)
        page = use_case.execute(ListGalleriesQuery(user_id=1, can_upload=True, limit=1))
        assert page.total == 2 and page.years == (2026, 2007)
        assert page.items[0].id == second and page.items[0].image_count == 0
        filtered = use_case.execute(ListGalleriesQuery(user_id=1, can_upload=True, year=2007))
        assert filtered.total == 1 and filtered.items[0].id == first
        assert filtered.items[0].image_count == 2
        all_items = use_case.execute(ListGalleriesQuery(user_id=1, can_upload=True, can_manage_media=True))
        assert all_items.total == 3 and all_items.years == (2026, 2007, 1999)


def test_update_metadata_order_cover_preserves_captions_and_files(engine):
    with Session(engine) as session:
        gallery_id = create(session)
        membership = session.get(GalleryMedia, (gallery_id, 42))
        membership.caption_override = "Behalten"
        session.add(membership)
        session.commit()
        old = build_get_gallery(session).execute(access(gallery_id))
        build_update_gallery(session).execute(update(old, title="Archiv", gallery_date=date(2008, 1, 1),
            show_date=False, media_ids=(42, 12), cover_image_id=12))
    with Session(engine) as session:
        current = build_get_gallery(session).execute(access(gallery_id))
        assert current.title == "Archiv" and current.gallery_date == date(2008, 1, 1)
        assert current.media_ids == (42, 12) and current.cover_image_id == 12
        assert current.show_date is False and current.updated_at != old.updated_at
        assert session.get(GalleryMedia, (gallery_id, 42)).caption_override == "Behalten"
        assert session.get(GalleryMedia, (gallery_id, 11)) is None
        assert session.get(MediaAsset, 11) is not None
        with pytest.raises(GalleryConflict):
            build_update_gallery(session).execute(update(old, title="Veraltet"))
        assert build_get_gallery(session).execute(access(gallery_id)).title == "Archiv"


def test_access_and_new_foreign_images_are_rejected(engine):
    with Session(engine) as session:
        session.add(User(id=2, email="second@example.test", name="Other", password_hash="test"))
        session.commit()
        gallery_id = create(session)
        current = build_get_gallery(session).execute(access(gallery_id))
        with pytest.raises(GalleryNotFound):
            build_get_gallery(session).execute(access(gallery_id, user_id=2))
        with pytest.raises(GalleryNotFound):
            build_update_gallery(session).execute(update(current, user_id=2))
        assert build_get_gallery(session).execute(access(gallery_id, user_id=2, can_manage_media=True)).id == gallery_id
        image = session.get(MediaAsset, 12)
        image.uploaded_by_user_id = 2
        session.add(image)
        session.commit()
        with pytest.raises(ImageNotFound):
            build_update_gallery(session).execute(update(current, media_ids=(11, 42, 12)))
        assert build_get_gallery(session).execute(access(gallery_id)).media_ids == (11, 42)


def test_invalid_cover_duplicate_membership_and_commit_failure_rollback(engine):
    with Session(engine) as session:
        gallery_id = create(session)
        old = build_get_gallery(session).execute(access(gallery_id))
        for changes in [dict(cover_image_id=12), dict(media_ids=(11, 11))]:
            with pytest.raises(GalleryError):
                build_update_gallery(session).execute(update(old, **changes))
        with patch.object(session, 'commit', side_effect=RuntimeError('failed')):
            with pytest.raises(RuntimeError):
                build_update_gallery(session).execute(update(old, title="Nicht speichern", media_ids=(), cover_image_id=None))
        current = build_get_gallery(session).execute(access(gallery_id))
        assert current.title == old.title and current.media_ids == old.media_ids
        build_update_gallery(session).execute(update(current, media_ids=(), cover_image_id=None))
        assert build_get_gallery(session).execute(access(gallery_id)).cover_image_id is None


def test_preview_requires_gallery_access_and_membership(engine):
    with Session(engine) as session:
        gallery_id = create(session)
        media, storage = Mock(), Mock()
        media.get_image.return_value = ImageReference("private.webp", 999)
        storage.read.return_value = b"image"
        use_case = GetGalleryImage(build_get_gallery(session), media, storage)
        assert use_case.execute(access(gallery_id), 42) == b"image"
        with pytest.raises(ImageNotFound):
            use_case.execute(access(gallery_id), 12)
        with pytest.raises(GalleryNotFound):
            use_case.execute(access(gallery_id, user_id=999), 42)
        assert storage.read.call_count == 1
