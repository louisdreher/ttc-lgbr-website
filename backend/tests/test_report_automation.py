import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from app.adapters.outbound.persistence.articles.models import Article, ArticleStatus
from app.adapters.outbound.persistence.events.models import Event
from app.adapters.outbound.persistence.messaging.models import OutboxMessage
from app.adapters.outbound.persistence.users.models import Role, User
from app.bootstrap.articles import (
    build_create_match_report_draft,
    build_edit_article_draft,
)
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
