"""Compose the existing article creation use case with SQL persistence."""

from sqlmodel import Session

from app.adapters.outbound.persistence.articles.unit_of_work import SqlArticleUnitOfWork
from app.core.content.articles.application.create_article import CreateArticle


def build_create_article(session: Session) -> CreateArticle:
    return CreateArticle(SqlArticleUnitOfWork(session))
