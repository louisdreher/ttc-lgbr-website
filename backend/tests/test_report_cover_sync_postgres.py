from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlmodel import Session, select

from test_gallery_creation_postgres import gallery_database, creation  # noqa: F401
from test_outbox_postgres import postgres_database  # noqa: F401
from app.adapters.outbound.persistence.articles.models import Article
from app.adapters.outbound.persistence.media.models import Gallery, GalleryMedia
from app.bootstrap.articles import build_save_article
from app.bootstrap.media import build_create_gallery
from app.core.content.articles.application.dto import ArticleActor, SaveArticleCommand


def test_concurrent_gallery_creation_and_report_save_keep_current_cover(gallery_database):
    barrier = Barrier(2)

    def create():
        with Session(gallery_database) as session:
            barrier.wait(timeout=5)
            return build_create_gallery(session).execute(creation()).id

    def save():
        with Session(gallery_database) as session:
            barrier.wait(timeout=5)
            return build_save_article(session).execute(SaveArticleCommand(
                actor=ArticleActor(user_id=900001, can_write=True, authenticated=True),
                article_id=5, event_id=7, title='Report', slug='report', content='Text', cover_image_id=11))

    with ThreadPoolExecutor(max_workers=2) as pool:
        creating, saving = pool.submit(create), pool.submit(save)
        gallery_id = creating.result(timeout=15)
        assert saving.result(timeout=15) == 5
    with Session(gallery_database) as session:
        assert session.get(Article, 5).cover_image_id == 11
        assert session.get(Gallery, gallery_id).cover_image_id == 11
        ids = session.exec(select(GalleryMedia.media_asset_id).where(GalleryMedia.gallery_id == gallery_id)).all()
        assert ids.count(11) == 1
