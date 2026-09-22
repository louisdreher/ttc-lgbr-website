from datetime import date, datetime, timezone
from unittest.mock import Mock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.adapters.inbound.http.auth.dependencies import get_current_user
from app.adapters.inbound.http.media.gallery_router import router
from app.adapters.inbound.http.media import dependencies as dep
from app.core.users.public import UserDetails
from app.core.content.media.application.dto import GalleryDetails, GalleryPage
from app.core.content.media.application.errors import GalleryConflict, GalleryNotFound


@pytest.fixture
def api():
    app = FastAPI()
    app.include_router(router)
    details = GalleryDetails(id=3, title="Archiv", event_id=None, gallery_date=date(2007, 6, 16),
        show_date=False, cover_image_id=11, image_count=1, media_ids=(11,),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc), created_by_user_id=7)
    read, listing, write, image = Mock(), Mock(), Mock(), Mock()
    read.execute.return_value = details
    listing.execute.return_value = GalleryPage((details,), 1, 0, 20, (2007,))
    image.execute.return_value = b"webp"
    def override(mock):
        return lambda: mock
    for provider, mock in [(dep.provide_get_gallery, read), (dep.provide_list_galleries, listing),
                           (dep.provide_update_gallery, write), (dep.provide_gallery_image, image)]:
        app.dependency_overrides[provider] = override(mock)
    return app, read, listing, write, image


def authenticate(app, role='TEAM_REPORTER'):
    app.dependency_overrides[get_current_user] = lambda: UserDetails(id=7, email="t@example.test", name="Test", is_active=True, roles=[role])


def body():
    return dict(title="Archiv", gallery_date="2007-06-16", show_date=False, media_ids=[11],
                cover_image_id=11, updated_at="2026-01-01T00:00:00Z")


def test_list_details_update_and_scoped_image(api):
    app, read, listing, write, image = api
    authenticate(app)
    client = TestClient(app)
    response = client.get('/api/admin/media/galleries?year=2007&offset=20')
    assert response.status_code == 200
    assert response.json()['years'] == [2007]
    assert response.headers['cache-control'] == 'private, no-store'
    query = listing.execute.call_args.args[0]
    assert query.user_id == 7 and not query.can_manage_media and query.year == 2007 and query.offset == 20
    assert client.get('/api/admin/media/galleries/3').json()['media_ids'] == [11]
    assert client.put('/api/admin/media/galleries/3', json=body()).status_code == 204
    assert write.execute.call_args.args[0].media_ids == (11,)
    assert write.execute.call_args.args[0].updated_at.tzinfo is not None
    preview = client.get('/api/admin/media/galleries/3/images/11')
    assert preview.status_code == 200 and preview.content == b'webp'
    assert preview.headers['content-type'] == 'image/webp'


@pytest.mark.parametrize('role,status', [(None, 401), ('MEMBER', 403)])
def test_management_requires_writer_role(api, role, status):
    app, read, listing, write, image = api
    if role:
        authenticate(app, role)
    client = TestClient(app)
    assert client.get('/api/admin/media/galleries').status_code == status
    assert client.get('/api/admin/media/galleries/3').status_code == status
    assert client.put('/api/admin/media/galleries/3', json=body()).status_code == status
    assert client.get('/api/admin/media/galleries/3/images/11').status_code == status
    for mock in (read, listing, write, image):
        mock.execute.assert_not_called()


def test_validation_conflict_and_missing_gallery(api):
    app, read, listing, write, image = api
    authenticate(app, 'EDITOR')
    client = TestClient(app)
    assert client.get('/api/admin/media/galleries?year=0').status_code == 422
    assert client.put('/api/admin/media/galleries/3', json=body() | {'event_id': 7}).status_code == 422
    assert client.put('/api/admin/media/galleries/3', json=body() | {'updated_at': '2026-01-01'}).status_code == 422
    write.execute.side_effect = GalleryConflict('Geändert')
    assert client.put('/api/admin/media/galleries/3', json=body()).status_code == 409
    assert write.execute.call_args.args[0].can_manage_media is True
    read.execute.side_effect = GalleryNotFound()
    assert client.get('/api/admin/media/galleries/3').status_code == 404
