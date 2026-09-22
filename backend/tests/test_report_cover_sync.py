from unittest.mock import patch

import pytest
from sqlmodel import Session, select

from test_gallery_repository import engine  # noqa: F401
from test_gallery_creation_sql import seed_report, creation
from app.adapters.outbound.persistence.articles.models import Article
from app.adapters.outbound.persistence.media.models import Gallery, GalleryMedia
from app.bootstrap.articles import build_save_article
from app.bootstrap.media import build_create_gallery, build_get_gallery, build_update_gallery
from app.core.content.articles.application.dto import ArticleActor, SaveArticleCommand
from app.core.content.media.application.dto import GetGalleryQuery, UpdateGalleryCommand
from app.core.content.media.application.errors import GalleryConflict


def save_cover(session, media_id, *, submit=False):
    return build_save_article(session, submit=submit).execute(command(media_id))


def command(media_id):
    return SaveArticleCommand(actor=ArticleActor(user_id=1, can_write=True, authenticated=True),
        article_id=5, event_id=7, title='Bericht', slug='bericht', content='Text', cover_image_id=media_id)


def gallery_state(session, gallery_id):
    gallery = session.get(Gallery, gallery_id, populate_existing=True)
    members = session.exec(select(GalleryMedia).where(GalleryMedia.gallery_id == gallery_id)
        .order_by(GalleryMedia.sort_order)).all()
    return gallery.cover_image_id, tuple(m.media_asset_id for m in members), gallery.updated_at


@pytest.mark.parametrize('submit', [False, True])
def test_cover_change_adds_image_preserves_old_images_and_advances_version(engine, submit):
    seed_report(engine, system=True)
    with Session(engine) as session:
        gallery_id = build_create_gallery(session).execute(creation(media_ids=(42,))).id
        before = gallery_state(session, gallery_id)
        save_cover(session, 11, submit=submit)
        after = gallery_state(session, gallery_id)
        assert after[:2] == (11, (42, 11)) and after[2] > before[2]
        # Re-selecting a member does not duplicate it or change its position.
        save_cover(session, 42)
        assert gallery_state(session, gallery_id)[:2] == (42, (42, 11))
        unchanged = gallery_state(session, gallery_id)
        save_cover(session, 42)
        assert gallery_state(session, gallery_id) == unchanged
        save_cover(session, None)
        assert gallery_state(session, gallery_id) == unchanged


def test_saving_cover_does_not_create_gallery_and_later_creation_adopts_it(engine):
    seed_report(engine, system=True)
    with Session(engine) as session:
        save_cover(session, 11)
        assert session.exec(select(Gallery)).all() == []
        gallery_id = build_create_gallery(session).execute(creation(media_ids=())).id
        assert gallery_state(session, gallery_id)[:2] == (11, (11,))


def test_sync_failure_rolls_back_both_report_and_gallery(engine):
    seed_report(engine, system=True)
    with Session(engine) as session:
        gallery_id = build_create_gallery(session).execute(creation(media_ids=(42,))).id
        before = gallery_state(session, gallery_id)
        use_case = build_save_article(session)
        adopt = use_case.uow.gallery_covers.adopt

        def fail_after_update(event_id, media_id):
            adopt(event_id, media_id)
            raise RuntimeError('Simulated failure after gallery update')

        with patch.object(use_case.uow.gallery_covers, 'adopt', side_effect=fail_after_update):
            with pytest.raises(RuntimeError):
                use_case.execute(command(11))
        assert session.get(Article, 5, populate_existing=True).cover_image_id == 42
        assert gallery_state(session, gallery_id) == before


def test_stale_gallery_form_cannot_overwrite_synced_cover(engine):
    seed_report(engine, system=True)
    with Session(engine) as session:
        gallery_id = build_create_gallery(session).execute(creation(media_ids=(42,))).id
        before = build_get_gallery(session).execute(GetGalleryQuery(gallery_id=gallery_id, user_id=1, can_upload=True))
        save_cover(session, 11)
        with pytest.raises(GalleryConflict):
            build_update_gallery(session).execute(UpdateGalleryCommand(
                gallery_id=gallery_id, user_id=1, can_upload=True, title=before.title,
                gallery_date=before.gallery_date, show_date=before.show_date,
                media_ids=before.media_ids, cover_image_id=before.cover_image_id, updated_at=before.updated_at))
        assert gallery_state(session, gallery_id)[:2] == (11, (42, 11))
