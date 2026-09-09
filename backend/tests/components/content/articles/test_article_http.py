import ast
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import app.model_registry  # noqa: F401 -- register foreign-key targets
from app.adapters.inbound.http.articles.admin_router import article_editor, router
from app.adapters.outbound.persistence.articles.models import Article as ArticleRecord
from app.adapters.outbound.persistence.articles.repository import (
    SQLModelArticleRepository,
)
from app.adapters.outbound.persistence.articles.unit_of_work import SqlArticleUnitOfWork
from app.adapters.outbound.persistence.database import get_session
from app.adapters.outbound.persistence.users.models import User
from app.bootstrap.articles import build_create_article
from app.core.content.articles.application.dto import CreateArticleCommand
from app.core.content.articles.domain.article import (
    Article,
    ArticleStatus,
    ArticleType,
    Visibility,
)
from app.core.users.public import UserDetails


@pytest.fixture
def article_database():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            User(
                id=1,
                email="editor@example.org",
                name="Editor",
                password_hash="test-only",
            )
        )
        session.commit()
    yield engine
    engine.dispose()


@pytest.fixture
def client(article_database):
    app = FastAPI()
    app.include_router(router)

    def test_session():
        with Session(article_database) as session:
            yield session

    app.dependency_overrides[get_session] = test_session
    app.dependency_overrides[article_editor] = lambda: UserDetails(
        id=1,
        email="editor@example.org",
        name="Editor",
        is_active=True, roles=["EDITOR"],
    )
    with TestClient(app) as client:
        yield client


def payload(**changes):
    data = {
        "title": " Turnier ",
        "slug": " TURNIER ",
        "teaser": " Vorschau ",
        "content": " Inhalt ",
    }
    return data | changes


def test_http_creates_draft_and_uses_authenticated_author(client, article_database):
    response = client.post(
        "/api/admin/articles", json=payload(author_id=999, status="PUBLISHED")
    )
    assert response.status_code == 201, response.text
    assert response.json() == {
        "id": 1,
        "title": "Turnier",
        "slug": "turnier",
        "status": "DRAFT",
    }
    with Session(article_database) as session:
        article = session.exec(select(ArticleRecord)).one()
        assert article.author_id == 1
        assert article.published_at is None
        assert article.content == "Inhalt"


def test_http_slug_conflict_and_domain_validation(client):
    assert client.post("/api/admin/articles", json=payload()).status_code == 201
    assert client.post("/api/admin/articles", json=payload()).status_code == 409
    assert (
        client.post(
            "/api/admin/articles", json=payload(slug="neu", title=" ")
        ).status_code
        == 422
    )


def test_repository_flush_does_not_commit(article_database):
    with Session(article_database) as session:
        article = Article.create_draft(
            author_id=1,
            title="Turnier",
            slug="turnier",
            teaser="Vorschau",
            content="Inhalt",
            article_type=ArticleType.NEWS,
            visibility=Visibility.PUBLIC,
        )
        saved = SQLModelArticleRepository(session).save(article)
        assert saved.id is not None
        assert saved.status == ArticleStatus.DRAFT
        session.rollback()
    with Session(article_database) as session:
        assert session.exec(select(ArticleRecord)).all() == []


def test_commit_failure_rolls_back_flushed_article(article_database):
    with Session(article_database) as session:
        use_case = build_create_article(session)
        command = CreateArticleCommand(
            author_id=1,
            title="Turnier",
            slug="turnier",
            teaser="Vorschau",
            content="Inhalt",
            article_type=ArticleType.NEWS,
            visibility=Visibility.PUBLIC,
        )
        with (
            patch.object(
                SqlArticleUnitOfWork,
                "commit",
                side_effect=RuntimeError("commit failed"),
            ),
            pytest.raises(RuntimeError, match="commit failed"),
        ):
            use_case.execute(command)
        assert not session.in_transaction()
    with Session(article_database) as session:
        assert session.exec(select(ArticleRecord)).all() == []


def test_article_core_does_not_import_frameworks_or_adapters():
    root = Path(__file__).resolve().parents[4] / "app/core/content/articles"
    assert root.is_dir()
    for path in root.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            elif isinstance(node, ast.Import):
                modules = [name.name for name in node.names]
            else:
                continue
            for module in modules:
                assert not module.startswith(
                    (
                        "sqlmodel",
                        "sqlalchemy",
                        "fastapi",
                        "pydantic",
                        "app.adapters",
                        "app.bootstrap",
                    )
                ), (path, module)
                if path.parent.name == "domain":
                    assert "application" not in module, (path, module)
