from app.adapters.outbound.persistence.articles.repository import (
    SQLModelArticleRepository,
)
from app.adapters.outbound.persistence.database import get_session
from app.core.content.articles.application.create_article import (
    CreateArticle,
)
from fastapi import Depends
from sqlmodel import Session


def get_create_article(
    session: Session = Depends(get_session),
) -> CreateArticle:
    repository = SQLModelArticleRepository(session)
    return CreateArticle(repository)
