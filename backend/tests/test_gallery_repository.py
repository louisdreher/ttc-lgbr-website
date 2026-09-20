from datetime import date
from datetime import datetime, timezone

import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select

import app.model_registry  # noqa: F401 -- register all foreign-key targets
from app.adapters.outbound.persistence.events.models import Event, EventCategory
from app.adapters.outbound.persistence.media.gallery_repository import SqlGalleryRepository
from app.adapters.outbound.persistence.media.models import Gallery as GalleryRow
from app.adapters.outbound.persistence.media.models import GalleryMedia, MediaAsset
from app.adapters.outbound.persistence.users.models import User
from app.core.content.media.domain.gallery import Gallery


@pytest.fixture
def engine():
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(id=1, email="gallery@example.test", name="Editor", password_hash="test"))
        session.add(EventCategory(id=1, name="Turnier", slug="turnier"))
        session.flush()
        session.add(Event(id=7, title="Turnier", starts_at=datetime.now(timezone.utc), category_id=1))
        for media_id in (11, 12, 42):
            session.add(MediaAsset(
                id=media_id, storage_key=f"images/{media_id}.webp", original_filename="test.png",
                mime_type="image/webp", file_size=10, width=10, height=10, uploaded_by_user_id=1,
            ))
        session.commit()
    yield engine
    engine.dispose()


def test_stores_gallery_cover_and_order_in_existing_tables(engine):
    gallery = Gallery(gallery_date=date(2026, 9, 20), title=" Turnier ", event_id=7, media_ids=(42, 11, 12), cover_image_id=11)
    with Session(engine) as session:
        repository = SqlGalleryRepository(session)
        assert not repository.exists_for_event(7)
        saved = repository.save(gallery, created_by_user_id=1)
        assert saved.id is not None and gallery.id is None
        assert repository.exists_for_event(7)
        assert not repository.exists_for_event(999)
        session.commit()
    with Session(engine) as session:
        row = session.get(GalleryRow, saved.id)
        assert (row.title, row.event_id, row.cover_image_id, row.created_by_user_id) == ("Turnier", 7, 11, 1)
        assert row.gallery_date == date(2026, 9, 20)
        assert row.show_date is True
        members = session.exec(select(GalleryMedia).where(
            GalleryMedia.gallery_id == saved.id
        ).order_by(GalleryMedia.sort_order)).all()
        assert [(item.media_asset_id, item.sort_order) for item in members] == [(42, 0), (11, 1), (12, 2)]
        assert all(item.caption_override is None for item in members)


def test_rollback_removes_gallery_and_memberships_but_keeps_media(engine):
    with Session(engine) as session:
        SqlGalleryRepository(session).save(
            Gallery(gallery_date=date(2026, 9, 20), title="Turnier", media_ids=(11, 12)), created_by_user_id=1
        )
        session.rollback()
    with Session(engine) as session:
        assert session.exec(select(GalleryRow)).all() == []
        assert session.exec(select(GalleryMedia)).all() == []
        assert len(session.exec(select(MediaAsset)).all()) == 3


def test_multiple_empty_standalone_galleries_are_allowed(engine):
    with Session(engine) as session:
        repository = SqlGalleryRepository(session)
        first = repository.save(Gallery(gallery_date=date(2007, 6, 16), show_date=False, title="Eins"), created_by_user_id=1)
        second = repository.save(Gallery(gallery_date=date(2026, 9, 20), title="Zwei"), created_by_user_id=1)
        session.commit()
        assert first.id != second.id
        assert session.get(GalleryRow, first.id).gallery_date == date(2007, 6, 16)
        assert session.get(GalleryRow, first.id).show_date is False
        assert first.cover_image_id is second.cover_image_id is None
        assert session.exec(select(GalleryMedia)).all() == []


def test_unique_event_constraint_blocks_duplicate_gallery(engine):
    with Session(engine) as session:
        repository = SqlGalleryRepository(session)
        repository.save(Gallery(gallery_date=date(2026, 9, 20), title="Eins", event_id=7), created_by_user_id=1)
        session.commit()
        with pytest.raises(IntegrityError):
            repository.save(Gallery(gallery_date=date(2026, 9, 20), title="Zwei", event_id=7), created_by_user_id=1)
        session.rollback()
        assert len(session.exec(select(GalleryRow)).all()) == 1


def test_invalid_membership_can_be_rolled_back_with_gallery(engine):
    with Session(engine) as session:
        with pytest.raises(IntegrityError):
            SqlGalleryRepository(session).save(
                Gallery(gallery_date=date(2026, 9, 20), title="Turnier", media_ids=(11, 999), cover_image_id=11),
                created_by_user_id=1,
            )
        session.rollback()
        assert session.exec(select(GalleryRow)).all() == []
        assert session.exec(select(GalleryMedia)).all() == []


def test_rejects_updating_existing_gallery(engine):
    with Session(engine) as session:
        with pytest.raises(ValueError):
            SqlGalleryRepository(session).save(Gallery(gallery_date=date(2026, 9, 20), title="Turnier", id=1), created_by_user_id=1)
        assert session.exec(select(GalleryRow)).all() == []
