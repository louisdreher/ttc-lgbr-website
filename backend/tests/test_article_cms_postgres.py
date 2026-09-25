"""CMS migrations and races in disposable PostgreSQL databases."""
# ruff: noqa: F811 -- pytest injects the imported PostgreSQL fixture by name.

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier

import pytest
from alembic import command
from app.adapters.outbound.persistence.articles.models import Article
from app.adapters.outbound.persistence.events.models import Event, EventCategory
from app.adapters.outbound.persistence.users.models import User
from app.bootstrap.articles import build_create_match_report_draft, build_save_article
from app.core.content.articles.application.dto import (
    ArticleActor,
    CreateMatchReportDraftCommand,
    SaveArticleCommand,
)
from app.core.content.articles.application.errors import ArticleConflictError
from app.core.content.articles.domain.article import ArticleType
from sqlalchemy import text
from sqlmodel import Session, select
from test_outbox_postgres import postgres_database, seed_report_match  # noqa: F401


def seed(engine):
    with Session(engine) as session:
        system_id = session.exec(
            select(User.id).where(User.system_key == "article-automation")
        ).one()
        # This fixture also runs before the user-administration migration.
        # Use only historical columns, not today's ORM insert defaults.
        ids = [
            session.execute(
                text(
                    'INSERT INTO "user" '
                    '(email, name, password_hash, is_active, created_at) '
                    'VALUES (:email, :name, :password_hash, true, :created_at) '
                    'RETURNING id'
                ),
                {
                    "email": f"writer{i}@example.org",
                    "name": f"Writer {i}",
                    "password_hash": "!",
                    "created_at": datetime.now(timezone.utc),
                },
            ).scalar_one()
            for i in range(2)
        ]
        category = EventCategory(name="Verein", slug="verein")
        session.add(category)
        session.flush()
        event = Event(
            title="Fest", category_id=category.id, starts_at=datetime.now(timezone.utc)
        )
        session.add(event)
        session.flush()
        event_id = event.id
        session.commit()
        return event_id, ids, system_id


@pytest.mark.parametrize("system_draft", [False, True])
def test_parallel_writers_only_one_claims_event(postgres_database, system_draft):
    engine, config = postgres_database
    command.upgrade(config, "head")
    command.check(config)
    event_id, ids, system_id = seed(engine)
    if system_draft:
        with Session(engine) as session:
            session.add(
                Article(
                    author_id=system_id,
                    event_id=event_id,
                    title="System",
                    slug="system",
                    teaser="T",
                    content="C",
                    generation_key="test:1",
                )
            )
            session.commit()
    barrier = Barrier(2)

    def write(uid):
        with Session(engine) as session:
            use_case = build_save_article(session)
            barrier.wait(timeout=10)
            try:
                aid = use_case.execute(
                    SaveArticleCommand(
                        actor=ArticleActor(uid, True, False, True),
                        event_id=event_id,
                        title=f"Writer {uid}",
                        slug=f"report-{uid}",
                        content="Human text",
                    )
                )
                return uid, aid
            except ArticleConflictError:
                return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, ids))
    winners = [x for x in results if x is not None]
    assert len(winners) == 1
    with Session(engine) as session:
        article = session.exec(select(Article)).one()
        assert (article.author_id, article.id) == winners[0]
        assert article.content == "Human text"
        assert bool(article.generation_key) == system_draft


def test_upgrade_preserves_article_and_rejects_duplicate_event(postgres_database):
    engine, config = postgres_database
    command.upgrade(config, "b8d04e2f9513")
    event_id, ids, _ = seed(engine)
    with Session(engine) as session:
        session.add(
            Article(
                author_id=ids[0],
                event_id=event_id,
                title="Original",
                slug="original",
                teaser="T",
                content="C",
            )
        )
        session.commit()
    command.upgrade(config, "head")
    command.check(config)
    with Session(engine) as session:
        assert session.exec(select(Article)).one().title == "Original"
    command.downgrade(config, "b8d04e2f9513")
    with Session(engine) as session:
        session.add(
            Article(
                author_id=ids[1],
                event_id=event_id,
                title="Second",
                slug="second",
                teaser="T",
                content="C",
            )
        )
        session.commit()
    with pytest.raises(RuntimeError, match="Mehrere Artikel"):
        command.upgrade(config, "head")
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT COUNT(*) FROM article")).scalar_one() == 2
        )


def test_generation_does_not_overwrite_report_created_during_generation(
    postgres_database,
):
    engine, config = postgres_database
    command.upgrade(config, "head")
    _, ids, _ = seed(engine)
    match_id = seed_report_match(engine)
    with Session(engine) as session:
        event_id = session.exec(
            select(Event.id).where(Event.team_match_id == match_id)
        ).one()
    from app.adapters.outbound.articles.template import PlainTextMatchReportGenerator

    class Generator(PlainTextMatchReportGenerator):
        def generate(self, data):
            generated = super().generate(data)
            with Session(engine) as session:
                build_save_article(session).execute(
                    SaveArticleCommand(
                        actor=ArticleActor(ids[0], True, False, True),
                        event_id=event_id,
                        title="Human",
                        slug="human",
                        content="Keep this",
                        article_type=ArticleType.MATCH_REPORT,
                    )
                )
            return generated

    with Session(engine) as session:
        result = build_create_match_report_draft(
            session, generator=Generator()
        ).execute(CreateMatchReportDraftCommand(match_id))
        assert not result.created
        article = session.exec(select(Article)).one()
        assert article.author_id == ids[0] and article.content == "Keep this"
