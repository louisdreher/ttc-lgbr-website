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
