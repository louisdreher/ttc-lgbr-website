from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from sqlmodel import Session
from test_gallery_creation_postgres import gallery_database, creation  # noqa: F401
from test_outbox_postgres import postgres_database  # noqa: F401
from app.bootstrap.media import build_create_gallery, build_get_gallery, build_update_gallery, build_list_galleries
from app.core.content.media.application.dto import GetGalleryQuery, UpdateGalleryCommand, ListGalleriesQuery
from app.core.content.media.application.errors import GalleryConflict


def test_concurrent_updates_detect_stale_snapshot(gallery_database):
    with Session(gallery_database) as session:
        gallery_id = build_create_gallery(session).execute(creation()).id
        snapshot = build_get_gallery(session).execute(GetGalleryQuery(gallery_id=gallery_id, user_id=900001, can_upload=True))
        page = build_list_galleries(session).execute(ListGalleriesQuery(user_id=900001, can_upload=True, year=2007))
        assert page.total == 1 and page.items[0].image_count == 1
    barrier = Barrier(2)

    def edit(title):
        with Session(gallery_database) as session:
            barrier.wait(timeout=5)
            try:
                build_update_gallery(session).execute(UpdateGalleryCommand(
                    gallery_id=gallery_id, user_id=900001, can_upload=True, title=title,
                    gallery_date=snapshot.gallery_date, show_date=snapshot.show_date,
                    media_ids=snapshot.media_ids, cover_image_id=snapshot.cover_image_id, updated_at=snapshot.updated_at))
                return 'saved'
            except GalleryConflict:
                return 'conflict'

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(edit, name) for name in ('First', 'Second')]
        assert sorted(f.result(timeout=10) for f in futures) == ['conflict', 'saved']
