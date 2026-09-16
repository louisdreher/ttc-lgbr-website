import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from app.adapters.inbound.cli.content_worker import ContentWorker
from app.adapters.outbound.persistence.articles.models import Article, ArticleStatus
from app.adapters.outbound.persistence.events.models import Event
from app.adapters.outbound.persistence.messaging.models import OutboxMessage
from app.adapters.outbound.persistence.messaging.store import SqlOutboxStore, aware
from app.adapters.outbound.persistence.users.models import Role, User
from app.bootstrap.articles import (
    build_create_match_report_draft,
    build_edit_article_draft,
)
from app.bootstrap.messaging import build_process_outbox
from app.core.competition.application.events import ImportOrigin
from app.core.competition.application.sync.dto import ImportSummary, SyncMeetingCommand
from app.core.content.articles.application.dto import (
    CreateMatchReportDraftCommand,
    EditArticleDraftCommand,
)
from app.core.content.articles.application.errors import (
    ArticleAuthorError,
    ReportNotReadyError,
)
from app.core.content.articles.domain.errors import ArticleDomainError
from app.core.messaging.application.dto import ProcessingSummary, ProcessOutboxCommand
from sqlmodel import Session, select
from test_competition_imports import (  # noqa: F401 -- shared realistic import fixture
    imports,
    seed,
)

NOW = datetime(2026, 9, 15, tzinfo=timezone.utc)


@pytest.fixture
def reports(imports):  # noqa: F811 -- pytest injects the imported fixture
    engine, _, usecases, _ = imports
    match_id, _ = seed(imports)
    with Session(engine) as session:
        system = User(
            email="system@internal.invalid",
            name="System",
            password_hash="!",
            is_active=False,
            system_key="article-automation",
        )
        editor = User(
            email="editor@example.org",
            name="Redaktion",
            password_hash="!",
            roles=[Role(name="EDITOR")],
        )
        session.add(system)
        session.add(editor)
        session.commit()
        editor_id, system_id = editor.id, system.id
    return engine, usecases, match_id, editor_id, system_id


def import_details(reports, origin=ImportOrigin.CURRENT):
    _, usecases, match_id, _, _ = reports
    assert asyncio.run(
        usecases.meeting.execute(SyncMeetingCommand(match_id, import_origin=origin))
    )


def processor(engine, clock=lambda: NOW, generator=None):
    return build_process_outbox(
        session_factory=lambda: Session(engine), clock=clock, generator=generator
    )


def test_current_results_create_system_draft_with_sets(reports):
    engine, _, match_id, _, system_id = reports
    import_details(reports)
    assert processor(engine).execute(ProcessOutboxCommand()).succeeded == 1
    with Session(engine) as session:
        article = session.exec(select(Article)).one()
        assert article.author_id == system_id
        assert article.status == ArticleStatus.DRAFT and article.published_at is None
        assert "7:3" in article.title
        assert "Anna A" in article.content and "Bea B" in article.content
        assert "11:8" in article.content
        assert article.generation_key == f"team-match:{match_id}"
        assert article.generation_method == "match-data-template-v1"
        assert article.generated_at is not None
        assert article.event_id == session.exec(select(Event)).one().id
        assert session.exec(select(OutboxMessage)).one().processed_at is not None


@pytest.mark.parametrize(
    "origin,expected",
    [
        (ImportOrigin.HISTORY, True),
        (ImportOrigin.MANUAL, True),
        (ImportOrigin.CURRENT, False),
    ],
)
def test_automatic_filters_do_not_prevent_manual_generation(reports, origin, expected):
    engine, _, match_id, editor_id, _ = reports
    with Session(engine) as session:
        event = session.exec(select(Event)).one()
        event.report_expected = expected
        session.commit()
    import_details(reports, origin)
    assert processor(engine).execute(ProcessOutboxCommand()).succeeded == 1
    with Session(engine) as session:
        assert session.exec(select(Article)).all() == []
        result = build_create_match_report_draft(session).execute(
            CreateMatchReportDraftCommand(match_id, author_id=editor_id)
        )
        assert result.created
        assert session.get(Article, result.article_id).author_id == editor_id


def test_editor_takes_authorship_without_losing_origin_and_retry_preserves_text(
    reports,
):
    engine, _, match_id, editor_id, _ = reports
    import_details(reports)
    processor(engine).execute(ProcessOutboxCommand())
    with Session(engine) as session:
        article = session.exec(select(Article)).one()
        article_id, generated_at = article.id, article.generated_at
        build_edit_article_draft(session).execute(
            EditArticleDraftCommand(
                article_id,
                editor_id,
                "Neuer Titel",
                "Neuer Teaser",
                "Redaktioneller Text",
            )
        )
        # Simulate a crash after article commit and before the message acknowledgement.
        message = session.exec(select(OutboxMessage)).one()
        message.processed_at = None
        session.commit()
    broken_generator = Mock()
    broken_generator.generate.side_effect = RuntimeError(
        "Must not regenerate an existing article"
    )
    assert (
        processor(engine, generator=broken_generator)
        .execute(ProcessOutboxCommand())
        .succeeded
        == 1
    )
    broken_generator.generate.assert_not_called()
    with Session(engine) as session:
        articles = session.exec(select(Article)).all()
        assert len(articles) == 1
        article = articles[0]
        assert (
            article.author_id == editor_id and article.content == "Redaktioneller Text"
        )
        assert article.generation_key == f"team-match:{match_id}"
        assert article.generated_at == generated_at


def test_generation_failure_retries_and_does_not_insert_partial_article(reports):
    engine, _, _, _, _ = reports
    import_details(reports)
    clock = [NOW]
    generator = Mock()
    generator.generate.side_effect = RuntimeError("temporary failure")
    process = processor(engine, clock=lambda: clock[0], generator=generator)
    assert process.execute(ProcessOutboxCommand()).failed == 1
    with Session(engine) as session:
        message = session.exec(select(OutboxMessage)).one()
        assert message.attempts == 1 and message.last_error == "RuntimeError"
        assert message.failed_at is None and message.locked_until is None
        retry_at = aware(message.next_attempt_at)
        assert retry_at > NOW
        assert session.exec(select(Article)).all() == []
    assert process.execute(ProcessOutboxCommand()) == ProcessingSummary()
    clock[0] = retry_at
    process.handler.report_factory = lambda session: build_create_match_report_draft(
        session
    )
    assert process.execute(ProcessOutboxCommand()).succeeded == 1


def test_terminal_failure_can_be_released_manually(reports):
    engine, _, _, _, _ = reports
    import_details(reports)
    process = processor(engine)
    process.max_attempts = 1
    process.handler = Mock()
    process.handler.handle.side_effect = RuntimeError("broken")
    assert process.execute(ProcessOutboxCommand()).failed == 1
    store = SqlOutboxStore(lambda: Session(engine))
    with Session(engine) as session:
        message = session.exec(select(OutboxMessage)).one()
        event_id = message.event_id
        assert message.failed_at is not None
    assert process.execute(ProcessOutboxCommand()) == ProcessingSummary()
    store.retry(event_id, NOW)
    assert processor(engine).execute(ProcessOutboxCommand()).succeeded == 1
    with pytest.raises(ValueError, match="bereits verarbeitet"):
        store.retry(event_id, NOW)


def test_expired_lease_is_reclaimed_and_stale_worker_cannot_acknowledge(reports):
    engine, _, _, _, _ = reports
    import_details(reports)
    store = SqlOutboxStore(lambda: Session(engine))
    first = store.claim(NOW, timedelta(seconds=10), 5)
    assert first is not None
    assert store.claim(NOW, timedelta(seconds=10), 5) is None
    with pytest.raises(ValueError, match="gerade verarbeitet"):
        store.retry(first.event_id, NOW)
    second = store.claim(NOW + timedelta(seconds=11), timedelta(seconds=10), 5)
    assert second.event_id == first.event_id and second.lock_token != first.lock_token
    assert not store.complete(first, NOW + timedelta(seconds=12))
    assert store.complete(second, NOW + timedelta(seconds=12))


def test_exhausted_crash_attempts_become_visible_failures(reports):
    engine, _, _, _, _ = reports
    import_details(reports)
    store = SqlOutboxStore(lambda: Session(engine))
    assert store.claim(NOW, timedelta(seconds=1), 1)
    assert store.claim(NOW + timedelta(seconds=2), timedelta(seconds=1), 1) is None
    assert store.status()[0]["failed_at"] is not None


def test_invalid_message_does_not_block_the_next_one(reports):
    engine, _, _, _, _ = reports
    import_details(reports)
    with Session(engine) as session:
        session.add(
            OutboxMessage(
                event_id=uuid4(),
                event_type="unknown.v9",
                deduplication_key="invalid-test",
                occurred_at=NOW - timedelta(days=30),
                payload={},
            )
        )
        session.commit()
    summary = processor(engine).execute(ProcessOutboxCommand())
    assert summary == ProcessingSummary(succeeded=1, failed=1)


def test_report_requires_details_and_editor_permission(reports):
    engine, _, match_id, _, system_id = reports
    with Session(engine) as session:
        usecase = build_create_match_report_draft(session)
        with pytest.raises(ReportNotReadyError):
            usecase.execute(CreateMatchReportDraftCommand(match_id))
        with pytest.raises(ArticleAuthorError):
            usecase.execute(
                CreateMatchReportDraftCommand(match_id, author_id=system_id)
            )
        assert session.exec(select(Article)).all() == []


def test_published_article_cannot_be_edited_as_draft(reports):
    engine, _, _, editor_id, _ = reports
    import_details(reports)
    processor(engine).execute(ProcessOutboxCommand())
    with Session(engine) as session:
        article = session.exec(select(Article)).one()
        article.status = ArticleStatus.PUBLISHED
        session.commit()
        with pytest.raises(ArticleDomainError):
            build_edit_article_draft(session).execute(
                EditArticleDraftCommand(
                    article.id, editor_id, "Titel", "Teaser", "Inhalt"
                )
            )


def test_worker_processes_outbox_even_when_sync_fails():
    @contextmanager
    def acquire():
        yield True

    sync = AsyncMock(side_effect=RuntimeError("source offline"))
    process = Mock(return_value=ProcessingSummary(succeeded=1))
    worker = ContentWorker(
        sync, process, Mock(acquire=acquire), sync_interval=60, poll_interval=1
    )
    assert not asyncio.run(worker.once())
    process.assert_called_once()


def test_worker_skips_sync_owned_by_another_process():
    @contextmanager
    def acquire():
        yield False

    sync = AsyncMock(return_value=ImportSummary())
    worker = ContentWorker(
        sync,
        Mock(return_value=ProcessingSummary()),
        Mock(acquire=acquire),
        sync_interval=60,
        poll_interval=1,
    )
    assert asyncio.run(worker.once())
    sync.assert_not_awaited()


def test_system_identity_cannot_login_refresh_or_use_access_token_even_if_activated(
    reports,
):
    from unittest.mock import MagicMock

    from app.adapters.outbound.persistence.users.reader import SqlUserReader
    from app.core.auth.application.commands import Login, RefreshAccess
    from app.core.auth.application.dto import (
        CurrentUserQuery,
        LoginCommand,
        RefreshCommand,
    )
    from app.core.auth.application.queries import GetCurrentUser
    from app.core.auth.domain.session import AuthenticationError, RefreshSession

    engine, _, _, _, system_id = reports
    with Session(engine) as session:
        user = session.get(User, system_id)
        user.is_active = True
        session.commit()
        users = SqlUserReader(session)
        uow, passwords, tokens = MagicMock(), Mock(), Mock()
        passwords.verify.return_value = True
        with pytest.raises(AuthenticationError):
            Login(
                uow, users, passwords, tokens, timedelta(days=1), lambda: NOW
            ).execute(LoginCommand(email=user.email, password="anything"))
        passwords.verify.assert_not_called()
        tokens.decode_access.return_value = system_id
        with pytest.raises(AuthenticationError):
            GetCurrentUser(users, tokens).execute(CurrentUserQuery(access_token="test"))
        uow.sessions.get_for_update.return_value = RefreshSession(
            user_id=system_id, token_hash="test", expires_at=NOW + timedelta(days=1)
        )
        with pytest.raises(AuthenticationError):
            RefreshAccess(uow, users, tokens, timedelta(days=1), lambda: NOW).execute(
                RefreshCommand(refresh_token="test")
            )
        uow.commit.assert_not_called()
