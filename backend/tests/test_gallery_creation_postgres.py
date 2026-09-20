from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier
from unittest.mock import patch

import pytest
from alembic import command
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, select

from test_outbox_postgres import postgres_database  # noqa: F401
from app.adapters.outbound.persistence.articles.models import Article
from app.adapters.outbound.persistence.events.models import Event, EventCategory
from app.adapters.outbound.persistence.media.models import Gallery, GalleryMedia, MediaAsset
from app.adapters.outbound.persistence.users.models import User
from app.bootstrap.media import build_create_gallery
from app.core.content.media.application.dto import CreateGalleryCommand
from app.core.content.media.application.errors import EventGalleryAlreadyExists


@pytest.fixture
def gallery_database(postgres_database):
    engine, config = postgres_database
    command.upgrade(config, "head")
    with Session(engine) as session:
        session.add(User(id=900001, email="gallery@example.test", name="Writer", password_hash="test"))
        session.add(EventCategory(id=900001, name="Galerietest", slug="galerietest"))
        session.flush()
        session.add(Event(id=7, title="Event", category_id=900001,
                          starts_at=datetime(2007, 6, 15, 23, 30, tzinfo=timezone.utc)))
        for media_id in (11, 42):
            session.add(MediaAsset(
                id=media_id, storage_key=f"{media_id}.webp", original_filename="test.jpg",
                mime_type="image/webp", file_size=10, width=10, height=10,
                uploaded_by_user_id=900001,
            ))
        session.flush()
        session.add(Article(id=5, event_id=7, author_id=900001, title="Report",
                            slug="report", teaser="", content="Text", cover_image_id=42))
        session.commit()
    return engine


def creation():
    return CreateGalleryCommand(title="Galerie", user_id=900001, can_upload=True, event_id=7)


def test_concurrent_creation_commits_exactly_one_gallery(gallery_database):
    barrier = Barrier(2)

    def create():
        with Session(gallery_database) as session:
            barrier.wait(timeout=5)
            try:
                return build_create_gallery(session).execute(creation())
            except EventGalleryAlreadyExists:
                return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(create) for _ in range(2)]
        results = [future.result(timeout=10) for future in futures]
    assert sum(result is not None for result in results) == 1
    with Session(gallery_database) as session:
        assert len(session.exec(select(Gallery)).all()) == 1
        assert len(session.exec(select(GalleryMedia)).all()) == 1


def test_context_refreshes_cover_and_holds_event_and_report_locks(gallery_database):
    with Session(gallery_database) as session:
        stale = session.get(Article, 5)
        assert stale.cover_image_id == 42
        with Session(gallery_database) as writer:
            row = writer.get(Article, 5)
            row.cover_image_id = 11
            writer.add(row)
            writer.commit()
        uow = build_create_gallery(session).uow
        with uow:
            context = uow.events.for_creation(7, 900001)
            assert context.report_cover_image_id == 11
            for table, row_id in (("event", 7), ("article", 5)):
                with Session(gallery_database) as contender:
                    with pytest.raises(OperationalError) as error:
                        contender.execute(text(f"SELECT id FROM {table} WHERE id=:id FOR UPDATE NOWAIT"), {"id": row_id})
                    assert error.value.orig.sqlstate == "55P03"
        # Leaving without commit releases both locks by rollback.
        with Session(gallery_database) as contender:
            contender.execute(text("SELECT id FROM event WHERE id=7 FOR UPDATE NOWAIT"))
            contender.execute(text("SELECT id FROM article WHERE id=5 FOR UPDATE NOWAIT"))


def test_unique_constraint_is_translated_and_session_recovers(gallery_database):
    with Session(gallery_database) as session:
        use_case = build_create_gallery(session)
        use_case.execute(creation())
        with patch.object(use_case.uow.galleries, "exists_for_event", return_value=False):
            with pytest.raises(EventGalleryAlreadyExists):
                use_case.execute(creation())
        assert len(session.exec(select(Gallery)).all()) == 1
