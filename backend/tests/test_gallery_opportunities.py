from datetime import date, datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from test_gallery_repository import engine  # noqa: F401 -- isolated FK-enabled SQLite
from test_outbox_postgres import seed_report_match
from app.adapters.inbound.http.auth.dependencies import get_current_user
from app.adapters.inbound.http.media.dependencies import provide_gallery_opportunities
from app.adapters.inbound.http.media.router import router
from app.adapters.outbound.persistence.articles.models import Article, ArticleStatus
from app.adapters.outbound.persistence.events.models import Event
from app.adapters.outbound.persistence.media.models import Gallery
from app.bootstrap.media import build_gallery_opportunities
from app.core.content.media.application.dto import (
    GalleryOpportunitiesQuery, GalleryOpportunity, GalleryOpportunityPage,
)
from app.core.content.media.application.errors import GalleryAccessDenied
from app.core.content.media.application.queries import ListGalleryOpportunities
from app.core.content.media.domain.gallery import GalleryError
from app.core.users.public import UserDetails

NOW = datetime(2026, 9, 20, 12, tzinfo=timezone.utc)
URL = "/api/admin/media/galleries/opportunities"


def query(**changes):
    return GalleryOpportunitiesQuery(**({"user_id": 1, "can_upload": True, "as_of": NOW} | changes))


def test_filters_before_pagination_and_keeps_events_with_reports(engine):
    match_id = seed_report_match(engine)
    with Session(engine) as session:
        event = session.get(Event, 7)
        event.starts_at = NOW - timedelta(days=2)
        event.report_expected = True
        match = session.exec(select(Event).where(Event.team_match_id == match_id)).one()
        match.starts_at = NOW - timedelta(days=1)
        match.ends_at = None
        match.report_expected = True
        match_event_id = match.id
        for event_id, start, end, expected in [
            (20, NOW + timedelta(days=1), None, True),  # future
            (21, NOW - timedelta(hours=1), NOW + timedelta(hours=1), True),  # ongoing
            (22, NOW - timedelta(days=1), None, False),
            (23, NOW, None, True),  # exact boundary
            (24, NOW - timedelta(days=1), NOW, True),  # end boundary
            (25, NOW - timedelta(days=2), None, True),  # tie, larger ID first
            (26, NOW - timedelta(days=1), None, True),  # gallery already exists
        ]:
            session.add(Event(id=event_id, title=f"Event {event_id}", category_id=1,
                              starts_at=start, ends_at=end, report_expected=expected))
        session.flush()
        session.add(Gallery(event_id=26, title="Existing", gallery_date=date(2026, 9, 19), created_by_user_id=1))
        session.add(Article(event_id=7, author_id=1, title="Published", slug="published",
                            teaser="", content="Text", status=ArticleStatus.PUBLISHED))
        session.commit()
        use_case = build_gallery_opportunities(session)
        page = use_case.execute(query(limit=1))
        assert page.total == 2
        assert [item.event_id for item in page.items] == [25]
        second = use_case.execute(query(offset=1, limit=1))
        assert [item.event_id for item in second.items] == [7]
        games = use_case.execute(query(group="team_matches", limit=1))
        assert games.total == 1 and games.items[0].event_id == match_event_id
        assert games.items[0].team_match_id == match_id
        empty = use_case.execute(query(offset=99))
        assert empty.items == () and empty.total == 2
        # Creating a gallery removes the event on the next read.
        session.add(Gallery(event_id=7, title="New", gallery_date=date(2026, 9, 18), created_by_user_id=1))
        session.commit()
        assert use_case.execute(query()).total == 1


@pytest.mark.parametrize("changes,error", [
    ({"can_upload": False}, GalleryAccessDenied), ({"user_id": 0}, GalleryAccessDenied),
    ({"group": "invalid"}, GalleryError), ({"offset": -1}, GalleryError),
    ({"limit": 0}, GalleryError), ({"limit": 101}, GalleryError),
])
def test_query_guards(changes, error):
    reader = Mock()
    with pytest.raises(error):
        ListGalleryOpportunities(reader).execute(query(**changes))
    reader.opportunities.assert_not_called()


@pytest.fixture
def api():
    app = FastAPI()
    app.include_router(router)
    use_case = Mock()
    use_case.execute.return_value = GalleryOpportunityPage(
        (GalleryOpportunity(7, "Event", NOW, None, None),), 1, 0, 20,
    )
    app.dependency_overrides[provide_gallery_opportunities] = lambda: use_case
    return app, use_case


def authenticate(app, role):
    app.dependency_overrides[get_current_user] = lambda: UserDetails(
        id=8, email="test@example.test", name="Test", is_active=True, roles=[role],
    )


@pytest.mark.parametrize("role", ["ADMIN", "EDITOR", "TEAM_REPORTER"])
def test_http_defaults_and_identity(api, role):
    app, use_case = api
    authenticate(app, role)
    response = TestClient(app).get(URL)
    assert response.status_code == 200
    assert response.json()["items"][0]["event_id"] == 7
    assert response.json()["total"] == 1
    assert response.headers["Cache-Control"] == "private, no-store"
    received = use_case.execute.call_args.args[0]
    assert received.group == "other_events" and received.user_id == 8 and received.can_upload
    assert received.as_of.tzinfo is not None
    TestClient(app).get(URL + "?group=team_matches&offset=20&limit=10")
    received = use_case.execute.call_args.args[0]
    assert (received.group, received.offset, received.limit) == ("team_matches", 20, 10)


@pytest.mark.parametrize("role,status", [(None, 401), ("MEMBER", 403)])
def test_http_access(api, role, status):
    app, use_case = api
    if role:
        authenticate(app, role)
    assert TestClient(app).get(URL).status_code == status
    use_case.execute.assert_not_called()


@pytest.mark.parametrize("params", ["group=bad", "offset=-1", "limit=0", "limit=101"])
def test_http_validation(api, params):
    app, use_case = api
    authenticate(app, "EDITOR")
    assert TestClient(app).get(URL + "?" + params).status_code == 422
    use_case.execute.assert_not_called()


def test_http_database_error_is_generic(api):
    app, use_case = api
    authenticate(app, "EDITOR")
    use_case.execute.side_effect = SQLAlchemyError("private database details")
    response = TestClient(app).get(URL)
    assert response.status_code == 500
    assert "private database details" not in response.text
