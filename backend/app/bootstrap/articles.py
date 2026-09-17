"""Compose the existing article creation use case with SQL persistence."""

from app.adapters.outbound.persistence.articles.unit_of_work import SqlArticleUnitOfWork
from app.core.content.articles.application.create_article import CreateArticle
from sqlmodel import Session


def build_create_article(session: Session) -> CreateArticle:
    return CreateArticle(SqlArticleUnitOfWork(session))


def build_create_match_report_draft(
    session: Session, *, session_factory=None, generator=None
):
    from app.adapters.outbound.articles.authors import UserArticleAuthors
    from app.adapters.outbound.articles.match_data import CompetitionMatchReportReader
    from app.adapters.outbound.articles.template import PlainTextMatchReportGenerator
    from app.adapters.outbound.persistence.events.reader import SqlEventReader
    from app.adapters.outbound.persistence.users.reader import SqlUserReader
    from app.bootstrap.competition import build_get_match_details
    from app.core.content.articles.application.commands import CreateMatchReportDraft

    users = SqlUserReader(session)
    factory = session_factory or (lambda: Session(session.get_bind()))

    def get_match_event(match_id):
        with factory() as read_session:
            return SqlEventReader(
                read_session, SqlUserReader(read_session)
            ).get_by_match(match_id)

    return CreateMatchReportDraft(
        SqlArticleUnitOfWork(session),
        CompetitionMatchReportReader(build_get_match_details(factory), get_match_event),
        generator or PlainTextMatchReportGenerator(),
        UserArticleAuthors(users),
    )


def build_edit_article_draft(session: Session):
    from app.adapters.outbound.articles.authors import UserArticleAuthors
    from app.adapters.outbound.persistence.users.reader import SqlUserReader
    from app.core.content.articles.application.commands import EditArticleDraft

    return EditArticleDraft(
        SqlArticleUnitOfWork(session), UserArticleAuthors(SqlUserReader(session))
    )


def build_article_events(session: Session):
    from app.adapters.outbound.articles.events import EventArticleContext
    from app.adapters.outbound.persistence.events.reader import SqlEventReader
    from app.adapters.outbound.persistence.events.repository import (
        SqlCategoryRepository,
        SqlEventRepository,
    )
    from app.adapters.outbound.persistence.users.reader import SqlUserReader
    from app.bootstrap.competition import build_get_match_details
    from app.core.content.events.public import CreateHiddenArticleEvent

    return EventArticleContext(
        SqlEventReader(session, SqlUserReader(session)),
        CreateHiddenArticleEvent(
            SqlEventRepository(session), SqlCategoryRepository(session)
        ),
        build_get_match_details(lambda: Session(session.get_bind())),
    )


def build_article_reader(session: Session):
    from app.adapters.outbound.persistence.articles.reader import SqlArticleReader
    from app.adapters.outbound.persistence.users.reader import SqlUserReader

    return SqlArticleReader(session, SqlUserReader(session))


def build_save_article(session: Session, *, submit=False):
    from app.adapters.outbound.articles.authors import UserArticleAuthors
    from app.adapters.outbound.persistence.users.reader import SqlUserReader
    from app.core.content.articles.application.commands import (
        SaveArticle,
        SubmitArticle,
    )

    cls = SubmitArticle if submit else SaveArticle
    return cls(
        SqlArticleUnitOfWork(session),
        UserArticleAuthors(SqlUserReader(session)),
        build_article_events(session),
    )


def build_publish_article(session: Session):
    from app.core.content.articles.application.commands import PublishArticle

    return PublishArticle(SqlArticleUnitOfWork(session))


def build_manage_article(session: Session):
    from app.core.content.articles.application.commands import ManageArticle

    return ManageArticle(SqlArticleUnitOfWork(session))


def build_list_articles(session: Session):
    from app.core.content.articles.application.queries import ListArticles

    return ListArticles(build_article_reader(session))


def build_get_article(session: Session):
    from app.core.content.articles.application.queries import GetArticle

    return GetArticle(build_article_reader(session))


def build_article_opportunities(session: Session):
    from app.core.content.articles.application.queries import ListArticleOpportunities

    return ListArticleOpportunities(build_article_reader(session))


def build_prepare_article(session: Session):
    from app.core.content.articles.application.queries import PrepareArticleForEvent

    return PrepareArticleForEvent(
        build_article_reader(session), build_article_events(session)
    )
