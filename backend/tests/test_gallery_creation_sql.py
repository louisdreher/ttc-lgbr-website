from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from test_gallery_repository import engine  # noqa: F401 -- isolated database fixture
from app.adapters.outbound.persistence.articles.models import Article, ArticleStatus
from app.adapters.outbound.persistence.events.models import Event
from app.adapters.outbound.persistence.media.models import Gallery, GalleryMedia, MediaAsset
from app.adapters.outbound.persistence.users.models import User
from app.bootstrap.media import build_create_gallery
from app.core.content.media.application.dto import CreateGalleryCommand
from app.core.content.media.application.errors import GalleryAccessDenied


def creation(**changes):
    return CreateGalleryCommand(**({
        "title": "Turnier", "user_id": 1, "can_upload": True,
        "event_id": 7, "media_ids": (11, 42),
    } | changes))


def seed_report(engine, *, author_id=1, status=ArticleStatus.DRAFT, system=False):
    with Session(engine) as session:
        session.add(User(
            id=2, email="other@example.test", name="Other", password_hash="test",
            system_key="article-automation" if system else None,
        ))
        session.flush()
        event = session.get(Event, 7)
        event.starts_at = datetime(2007, 6, 15, 23, 30, tzinfo=timezone.utc)
        session.add(event)
        session.add(Article(
            id=5, event_id=7, author_id=author_id, title="Bericht", slug="bericht",
            teaser="", content="Text", cover_image_id=42, status=status,
        ))
        session.commit()


def test_creation_commits_date_cover_and_memberships(engine):
    seed_report(engine)
    with Session(engine) as session:
        result = build_create_gallery(session).execute(creation())
    with Session(engine) as session:
        gallery = session.get(Gallery, result.id)
        assert gallery.gallery_date == date(2007, 6, 16)
        assert gallery.show_date is True
        assert gallery.cover_image_id == 42
        assert [row.media_asset_id for row in session.exec(
            select(GalleryMedia).order_by(GalleryMedia.sort_order)
        )] == [11, 42]


@pytest.mark.parametrize("author_id,status,system,editor,allowed", [
    (1, ArticleStatus.DRAFT, False, False, True),
    (1, ArticleStatus.IN_REVIEW, False, False, True),
    (1, ArticleStatus.PUBLISHED, False, False, False),
    (1, ArticleStatus.ARCHIVED, False, False, False),
    (2, ArticleStatus.DRAFT, False, False, False),
    (2, ArticleStatus.DRAFT, True, False, True),
    (2, ArticleStatus.IN_REVIEW, True, False, False),
    (2, ArticleStatus.PUBLISHED, False, True, True),
])
def test_report_permissions(engine, author_id, status, system, editor, allowed):
    seed_report(engine, author_id=author_id, status=status, system=system)
    with Session(engine) as session:
        use_case = build_create_gallery(session)
        if allowed:
            use_case.execute(creation(can_manage_media=editor))
        else:
            with pytest.raises(GalleryAccessDenied):
                use_case.execute(creation(can_manage_media=editor))
            assert session.exec(select(Gallery)).first() is None


def test_event_without_report_requires_editor_and_missing_event_is_rejected(engine):
    with Session(engine) as session:
        use_case = build_create_gallery(session)
        with pytest.raises(GalleryAccessDenied):
            use_case.execute(creation())
        with pytest.raises(GalleryAccessDenied):
            use_case.execute(creation(event_id=999, can_manage_media=True))
        use_case.execute(creation(can_manage_media=True))


@pytest.mark.parametrize("failure", ["membership", "commit"])
def test_failure_rolls_back_gallery_and_all_memberships(engine, failure):
    seed_report(engine)
    with Session(engine) as session:
        use_case = build_create_gallery(session)
        if failure == "membership":
            save = use_case.uow.galleries.save

            def failing_save(gallery, **kwargs):
                saved = save(gallery, **kwargs)
                session.add(GalleryMedia(gallery_id=saved.id, media_asset_id=999, sort_order=3))
                session.flush()

            with patch.object(use_case.uow.galleries, "save", side_effect=failing_save):
                with pytest.raises(IntegrityError):
                    use_case.execute(creation())
        else:
            with patch.object(session, "commit", side_effect=RuntimeError("commit failed")):
                with pytest.raises(RuntimeError):
                    use_case.execute(creation())
        assert session.exec(select(Gallery)).first() is None
        assert session.exec(select(GalleryMedia)).first() is None
        assert session.get(MediaAsset, 42) is not None
        assert session.get(Article, 5).cover_image_id == 42
