from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import app.model_registry  # noqa: F401
import pytest
from app.adapters.inbound.http.articles.admin_router import router
from app.adapters.inbound.http.articles.public_router import member_router
from app.adapters.inbound.http.articles.public_router import router as public_router
from app.adapters.inbound.http.auth.dependencies import get_current_user
from app.adapters.outbound.persistence.articles.models import Article
from app.adapters.outbound.persistence.articles.unit_of_work import SqlArticleUnitOfWork
from app.adapters.outbound.persistence.database import get_session
from app.adapters.outbound.persistence.events.models import Event, EventCategory
from app.adapters.outbound.persistence.users.models import User
from app.core.users.public import UserDetails
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event as sql_event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select


@pytest.fixture
def cms():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @sql_event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        for uid in range(1, 6):
            session.add(
                User(
                    id=uid,
                    email=f"user{uid}@example.org",
                    name=f"User {uid}",
                    password_hash="!",
                    system_key="article-automation" if uid == 5 else None,
                )
            )
        session.add(EventCategory(id=1, name="Verein", slug="verein"))
        session.flush()
        session.add(
            Event(
                id=1,
                title="Vereinsfest",
                starts_at=datetime.now(timezone.utc),
                category_id=1,
                description="Ein gemeinsames Fest",
            )
        )
        session.commit()
    users = {
        "reporter": UserDetails(
            id=1,
            email="1@example.org",
            name="Reporter",
            is_active=True,
            roles=["TEAM_REPORTER"],
        ),
        "other": UserDetails(
            id=2,
            email="2@example.org",
            name="Other",
            is_active=True,
            roles=["TEAM_REPORTER"],
        ),
        "editor": UserDetails(
            id=3, email="3@example.org", name="Editor", is_active=True, roles=["EDITOR"]
        ),
        "admin": UserDetails(
            id=3, email="3@example.org", name="Admin", is_active=True, roles=["ADMIN"]
        ),
        "member": UserDetails(
            id=4, email="4@example.org", name="Member", is_active=True, roles=[]
        ),
    }
    current = [users["reporter"]]
    app = FastAPI()
    app.include_router(router)
    app.include_router(public_router)
    app.include_router(member_router)

    def session_dependency():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = session_dependency
    app.dependency_overrides[get_current_user] = lambda: current[0]
    with TestClient(app) as client:
        yield client, engine, lambda role: current.__setitem__(0, users[role])
    engine.dispose()


def test_opportunities_filter_time_and_paginate_groups_independently(cms):
    from test_outbox_postgres import seed_report_match

    client, engine, _ = cms
    match_id = seed_report_match(engine)
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        other = session.get(Event, 1)
        other.starts_at = now - timedelta(days=10)
        match = session.exec(select(Event).where(Event.team_match_id == match_id)).one()
        match.starts_at = now - timedelta(days=1)
        match.ends_at = None
        match_event_id = match.id
        session.add_all(
            [
                Event(title="Future", category_id=1, starts_at=now + timedelta(days=1)),
                Event(
                    title="Ongoing",
                    category_id=1,
                    starts_at=now - timedelta(hours=1),
                    ends_at=now + timedelta(hours=1),
                ),
            ]
        )
        session.commit()
    other = client.get(
        "/api/admin/articles/opportunities?group=other_events&limit=1"
    ).json()
    assert other["total"] == 1
    assert [item["event_id"] for item in other["other_events"]] == [1]
    assert other["team_matches"] == []
    games = client.get(
        "/api/admin/articles/opportunities?group=team_matches&limit=1"
    ).json()
    assert games["total"] == 1
    assert [item["event_id"] for item in games["team_matches"]] == [match_event_id]
    assert games["other_events"] == []
    with Session(engine) as session:
        session.get(Event, match_event_id).starts_at = now + timedelta(days=2)
        session.commit()
    assert (
        client.get("/api/admin/articles/opportunities?group=team_matches").json()[
            "total"
        ]
        == 0
    )
    assert (
        client.get("/api/admin/articles/opportunities?group=other_events").json()[
            "total"
        ]
        == 1
    )


def form(**changes):
    return (
        dict(title="Bericht", slug="bericht", teaser="Teaser", content="Inhalt")
        | changes
    )


def test_editorial_time_filter_applies_before_count_and_pagination(cms):
    client, engine, login = cms
    old_id = client.post("/api/admin/articles/save", json=form(slug="old")).json()["id"]
    fresh_id = client.post("/api/admin/articles/save", json=form(slug="fresh")).json()[
        "id"
    ]
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    with Session(engine) as session:
        old = session.get(Article, old_id)
        old.updated_at = cutoff - timedelta(seconds=1)
        fresh = session.get(Article, fresh_id)
        fresh.updated_at = cutoff
        session.add_all([old, fresh])
        session.commit()
    login("editor")
    result = client.get(
        "/api/admin/articles",
        params={
            "scope": "editorial",
            "updated_since": cutoff.isoformat(),
            "limit": 1,
        },
    )
    assert result.status_code == 200
    assert result.json()["total"] == 1
    assert result.json()["items"][0]["id"] == fresh_id
    assert (
        client.get("/api/admin/articles", params={"scope": "editorial"}).json()["total"]
        == 2
    )
    assert (
        client.get(
            "/api/admin/articles", params={"updated_since": "2026-09-01T00:00:00"}
        ).status_code
        == 422
    )


def test_reporter_workflow_and_editor_author_preservation(cms):
    client, engine, login = cms
    data = form(tags=["Jugend", "jugend", "Verein"])
    response = client.post("/api/admin/articles/save", json=data)
    assert response.status_code == 200, response.text
    aid = response.json()["id"]
    assert response.json()["tags"] == ["jugend", "verein"]
    assert client.post(f"/api/admin/articles/{aid}/publish").status_code == 403
    submitted = client.post(f"/api/admin/articles/{aid}/submit", json=data)
    assert submitted.json()["status"] == "IN_REVIEW"
    assert client.get("/api/admin/articles").json()["items"][0]["id"] == aid
    edited = client.put(f"/api/admin/articles/{aid}", json=data | {"content": "Neu"})
    assert edited.json()["status"] == "IN_REVIEW"
    assert client.get("/api/articles").json()["total"] == 0
    login("other")
    assert client.get("/api/admin/articles").json()["total"] == 0
    assert client.get(f"/api/admin/articles/{aid}").status_code == 404
    assert client.put(f"/api/admin/articles/{aid}", json=data).status_code == 403
    assert client.get("/api/admin/articles?scope=editorial").status_code == 403
    login("editor")
    assert client.get("/api/admin/articles?scope=editorial").json()["total"] == 1
    assert client.put(f"/api/admin/articles/{aid}", json=data).json()["author_id"] == 1
    published = client.post(f"/api/admin/articles/{aid}/publish")
    assert published.json()["status"] == "PUBLISHED"
    assert published.json()["published_at"] is not None
    login("reporter")
    assert client.get(f"/api/admin/articles/{aid}").json()["allowed_actions"] == []
    assert client.put(f"/api/admin/articles/{aid}", json=data).status_code == 403
    assert client.get("/api/articles/bericht").status_code == 200
    assert "author_id" not in client.get("/api/articles/bericht").json()


def test_prepare_is_read_only_and_save_claims_system_draft(cms):
    client, engine, login = cms
    empty = client.get("/api/admin/articles/prepare/1")
    assert empty.status_code == 200, empty.text
    assert empty.json()["article_id"] is None
    assert empty.json()["title"] == "Vereinsfest"
    assert empty.json()["content"] == "Ein gemeinsames Fest"
    with Session(engine) as session:
        assert session.exec(select(Article)).all() == []
        session.add(
            Article(
                author_id=5,
                title="Systemtext",
                slug="system",
                teaser="T",
                content="C",
                event_id=1,
                generation_key="test:1",
                generation_method="template",
            )
        )
        session.commit()
    prepared = client.get("/api/admin/articles/prepare/1").json()
    assert prepared["title"] == "Systemtext"
    assert client.get("/api/admin/articles/opportunities").json()["total"] == 1
    data = form(event_id=1, article_type="EVENT_REPORT")
    saved = client.post("/api/admin/articles/save", json=data)
    assert saved.status_code == 200, saved.text
    assert saved.json()["id"] == prepared["article_id"]
    assert saved.json()["author_id"] == 1 and saved.json()["generated"]
    assert client.get("/api/admin/articles/opportunities").json()["total"] == 0
    login("other")
    assert client.post("/api/admin/articles/save", json=data).status_code == 409
    assert client.get("/api/admin/articles/prepare/1").status_code == 409
    with Session(engine) as session:
        assert len(session.exec(select(Article)).all()) == 1


def test_hidden_event_and_article_rollback_together(cms):
    client, engine, login = cms
    data = form(
        new_event=dict(title="Intern", category_id=1, starts_at="2026-09-17T12:00:00Z")
    )
    with patch.object(
        SqlArticleUnitOfWork, "commit", side_effect=ValueError("failure")
    ):
        assert client.post("/api/admin/articles/save", json=data).status_code == 422
    with Session(engine) as session:
        assert len(session.exec(select(Event)).all()) == 1
        assert session.exec(select(Article)).all() == []
    saved = client.post("/api/admin/articles/submit", json=data)
    assert saved.status_code == 200, saved.text
    with Session(engine) as session:
        event = session.get(Event, saved.json()["event_id"])
        assert event.visibility == "HIDDEN" and event.created_by_user_id == 1


@pytest.mark.parametrize(
    "visibility,public_count,member_count",
    [
        ("PUBLIC", 1, 1),
        ("MEMBERS_ONLY", 0, 1),
        ("HIDDEN", 0, 0),
    ],
)
def test_public_and_member_visibility(cms, visibility, public_count, member_count):
    client, _, login = cms
    login("admin")
    aid = client.post(
        "/api/admin/articles/save", json=form(visibility=visibility)
    ).json()["id"]
    assert client.post(f"/api/admin/articles/{aid}/publish").status_code == 200
    login("member")
    assert client.post("/api/admin/articles/save", json=form()).status_code == 403
    assert client.get("/api/admin/articles").status_code == 403
    assert client.get("/api/articles").json()["total"] == public_count
    assert client.get("/api/intern/articles").json()["total"] == member_count
    assert client.get("/api/articles/bericht").status_code == (
        200 if public_count else 404
    )
    assert client.get("/api/intern/articles/bericht").status_code == (
        200 if member_count else 404
    )


def test_incomplete_drafts_and_invalid_references(cms):
    client, _, login = cms
    data = form(teaser="", content="")
    aid = client.post("/api/admin/articles/save", json=data).json()["id"]
    assert (
        client.post(f"/api/admin/articles/{aid}/submit", json=data).status_code == 422
    )
    assert client.get(f"/api/admin/articles/{aid}").json()["status"] == "DRAFT"
    assert (
        client.post("/api/admin/articles/save", json=form(event_id=999)).status_code
        == 404
    )
    assert (
        client.post(
            "/api/admin/articles/save", json=form(slug="image", cover_image_id=999)
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/admin/articles/save",
            json=form(slug="match", article_type="MATCH_REPORT"),
        ).status_code
        == 422
    )
    assert (
        client.post("/api/admin/articles/save", json=form(slug=" ")).status_code == 422
    )
    assert client.get("/api/admin/articles?limit=101").status_code == 422


def test_submit_new_and_pagination(cms):
    client, _, login = cms
    for index in range(3):
        response = client.post(
            "/api/admin/articles/submit", json=form(slug=f"report-{index}")
        )
        assert response.status_code == 200, response.text
    page = client.get("/api/admin/articles?status=IN_REVIEW&limit=2&offset=1").json()
    assert page["total"] == 3 and len(page["items"]) == 2
    assert client.get("/api/admin/articles?status=DRAFT").json()["total"] == 0
    client.post("/api/admin/articles/save", json=form(slug="draft"))
    combined = client.get("/api/admin/articles?status=DRAFT&status=IN_REVIEW").json()
    assert combined["total"] == 4


def test_match_type_and_assignment_are_protected(cms):
    from test_outbox_postgres import seed_report_match

    client, engine, _ = cms
    match_id = seed_report_match(engine)
    with Session(engine) as session:
        event_id = session.exec(
            select(Event.id).where(Event.team_match_id == match_id)
        ).one()
    prepared = client.get(f"/api/admin/articles/prepare/{event_id}").json()
    assert prepared["article_type"] == "MATCH_REPORT"
    assert "article_type" not in prepared["editable_fields"]
    groups = client.get("/api/admin/articles/opportunities").json()
    assert len(groups["team_matches"]) == 1 and len(groups["other_events"]) == 1
    data = form(event_id=event_id, article_type="MATCH_REPORT")
    saved = client.post("/api/admin/articles/save", json=data)
    assert saved.status_code == 200, saved.text
    aid = saved.json()["id"]
    assert (
        client.put(
            f"/api/admin/articles/{aid}", json=data | {"article_type": "NEWS"}
        ).status_code
        == 422
    )
    assert (
        client.put(
            f"/api/admin/articles/{aid}", json=data | {"event_id": 1}
        ).status_code
        == 422
    )


def test_publishing_preserves_cover_and_tags(cms):
    from app.adapters.outbound.persistence.media.models import MediaAsset

    client, engine, login = cms
    with Session(engine) as session:
        media = MediaAsset(
            storage_key="test",
            original_filename="test.jpg",
            mime_type="image/jpeg",
            file_size=10,
            uploaded_by_user_id=1,
        )
        session.add(media)
        session.commit()
        image_id = media.id
    aid = client.post(
        "/api/admin/articles/submit",
        json=form(cover_image_id=image_id, tags=["verein"]),
    ).json()["id"]
    login("editor")
    published = client.post(f"/api/admin/articles/{aid}/publish").json()
    assert published["cover_image_id"] == image_id and published["tags"] == ["verein"]


def test_teaser_is_optional_when_submitting_and_publishing(cms):
    client, _, login = cms
    saved = client.post("/api/admin/articles/submit", json=form(teaser=""))
    assert saved.status_code == 200, saved.text
    login("editor")
    published = client.post(f"/api/admin/articles/{saved.json()['id']}/publish")
    assert published.status_code == 200 and published.json()["teaser"] == ""


def test_editorial_actions_preserve_content_and_restore_as_draft(cms):
    client, _, login = cms
    article = client.post(
        "/api/admin/articles/submit", json=form(event_id=1, tags=["verein"])
    ).json()
    aid = article["id"]
    for action in ("archive", "restore"):
        assert client.post(f"/api/admin/articles/{aid}/{action}").status_code == 403
    assert client.delete(f"/api/admin/articles/{aid}").status_code == 403
    assert (
        client.patch(
            f"/api/admin/articles/{aid}/visibility", json={"visibility": "HIDDEN"}
        ).status_code
        == 403
    )
    login("admin")
    assert client.post(f"/api/admin/articles/{aid}/publish").status_code == 200
    updated = client.patch(
        f"/api/admin/articles/{aid}/visibility", json={"visibility": "MEMBERS_ONLY"}
    ).json()
    assert (
        updated["content"] == article["content"]
        and updated["author_id"] == article["author_id"]
    )
    assert updated["tags"] == ["verein"] and updated["status"] == "PUBLISHED"
    archived = client.post(f"/api/admin/articles/{aid}/archive").json()
    assert archived["status"] == "ARCHIVED"
    assert set(archived["allowed_actions"]) == {"restore", "delete", "visibility"}
    assert client.get("/api/intern/articles").json()["total"] == 0
    assert client.get("/api/admin/articles/opportunities").json()["total"] == 0
    restored = client.post(f"/api/admin/articles/{aid}/restore").json()
    assert restored["status"] == "DRAFT" and restored["published_at"] is None
    assert restored["author_id"] == article["author_id"]
    assert client.get("/api/intern/articles").json()["total"] == 0


def test_delete_removes_only_article_and_links(cms):
    from app.adapters.outbound.persistence.articles.models import ArticleTag, Tag

    client, engine, login = cms
    aid = client.post(
        "/api/admin/articles/save", json=form(event_id=1, tags=["verein"])
    ).json()["id"]
    login("editor")
    assert client.delete(f"/api/admin/articles/{aid}").status_code == 204
    assert client.get(f"/api/admin/articles/{aid}").status_code == 404
    assert client.get("/api/admin/articles/opportunities").json()["total"] == 1
    with Session(engine) as session:
        assert session.get(Event, 1) is not None
        assert session.exec(select(ArticleTag)).all() == []
        assert len(session.exec(select(Tag)).all()) == 1


def test_round_match_slug_is_derived_and_independent_of_title(cms):
    from app.adapters.outbound.persistence.competition.matches import TeamMatch
    from app.adapters.outbound.persistence.competition.teams import Team
    from test_outbox_postgres import seed_report_match

    client, engine, _ = cms
    match_id = seed_report_match(engine)
    with Session(engine) as session:
        match = session.get(TeamMatch, match_id)
        match.scheduled_at = datetime(2026, 9, 17, 22, 30, tzinfo=timezone.utc)
        team = session.get(Team, match.team_id)
        team.name, team.team_number = "Herren", 2
        event_id = session.exec(
            select(Event.id).where(Event.team_match_id == match_id)
        ).one()
        session.commit()
    prepared = client.get(f"/api/admin/articles/prepare/{event_id}").json()
    assert prepared["slug"] == "herren-2-2026-09-18"
    assert "slug" not in prepared["editable_fields"]
    data = form(
        event_id=event_id,
        article_type="MATCH_REPORT",
        title="Ein Sieg",
        slug="ein-sieg",
    )
    saved = client.post("/api/admin/articles/save", json=data).json()
    assert saved["slug"] == prepared["slug"]
    updated = client.put(
        f"/api/admin/articles/{saved['id']}",
        json=data | {"title": "Anderer Titel", "slug": "anderer-titel"},
    ).json()
    assert updated["title"] == "Anderer Titel" and updated["slug"] == prepared["slug"]
