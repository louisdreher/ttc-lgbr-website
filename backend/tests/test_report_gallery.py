from unittest.mock import Mock

import pytest
from sqlmodel import Session

from test_gallery_repository import engine  # noqa: F401
from test_gallery_creation_sql import seed_report, creation
from app.adapters.outbound.persistence.articles.repository import SQLModelArticleRepository
from app.adapters.outbound.persistence.articles.models import Article, ArticleStatus
from app.adapters.outbound.persistence.media.models import MediaAsset
from app.bootstrap.media import build_create_gallery, build_get_event_gallery, build_get_gallery
from app.adapters.outbound.persistence.media.reader import SqlMediaReader
from app.core.content.media.application.dto import GetEventGalleryQuery, GetGalleryQuery
from app.core.content.media.application.errors import GalleryAccessDenied, GalleryNotFound, ImageNotFound
from app.core.content.media.application.queries import GetEventGalleryImage
from app.core.content.articles.domain.errors import ArticleDomainError


def query(**changes):
    return GetEventGalleryQuery(**(dict(event_id=7, user_id=1, can_upload=True) | changes))


def setup_gallery(engine):
    seed_report(engine)
    with Session(engine) as session:
        image = session.get(MediaAsset, 11)
        image.uploaded_by_user_id = 2
        image.caption = 'Gemeinsames Fest'
        session.add(image)
        session.commit()
        return build_create_gallery(session).execute(creation(user_id=2, can_manage_media=True))


def test_report_author_can_read_other_users_gallery_without_management_rights(engine):
    created = setup_gallery(engine)
    with Session(engine) as session:
        details = build_get_event_gallery(session).execute(query())
        assert details.id == created.id and details.media_ids == (11, 42)
        with pytest.raises(GalleryNotFound):
            build_get_gallery(session).execute(GetGalleryQuery(gallery_id=created.id, user_id=1, can_upload=True))


def test_only_editable_report_or_editor_grants_access(engine):
    setup_gallery(engine)
    with Session(engine) as session:
        read = build_get_event_gallery(session)
        with pytest.raises(GalleryAccessDenied):
            read.execute(query(user_id=2))
        article = session.get(Article, 5)
        article.status = ArticleStatus.PUBLISHED
        session.add(article)
        session.commit()
        with pytest.raises(GalleryAccessDenied):
            read.execute(query())
        assert read.execute(query(can_manage_media=True)) is not None
        with pytest.raises(GalleryNotFound):
            read.execute(query(event_id=999, can_manage_media=True))


def test_no_gallery_returns_none(engine):
    seed_report(engine)
    with Session(engine) as session:
        assert build_get_event_gallery(session).execute(query()) is None


def test_image_and_caption_access_stays_scoped_to_event_membership(engine):
    setup_gallery(engine)
    storage = Mock()
    storage.read.return_value = b'webp'
    with Session(engine) as session:
        images = GetEventGalleryImage(build_get_event_gallery(session), SqlMediaReader(session), storage)
        assert images.execute(query(), 11) == b'webp'
        caption = images.caption(query(), 11)
        assert caption.caption == 'Gemeinsames Fest' and not caption.can_edit
        assert images.caption(query(), 42).can_edit
        for media_id in (12, 999):
            with pytest.raises(ImageNotFound):
                images.execute(query(), media_id)
        storage.read.assert_called_once_with('images/11.webp')


def test_cover_validation_accepts_only_actual_event_gallery(engine):
    setup_gallery(engine)
    with Session(engine) as session:
        repository = SQLModelArticleRepository(session)
        repository.validate_cover(11, user_id=1, can_edit_all=False, event_id=7)
        for event_id in (None, 999):
            with pytest.raises(ArticleDomainError):
                repository.validate_cover(11, user_id=1, can_edit_all=False, event_id=event_id)
        repository.validate_cover(12, user_id=1, can_edit_all=False)
