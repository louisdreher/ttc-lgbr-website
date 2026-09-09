from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from app.adapters.outbound.persistence.database import get_session
from app.bootstrap.articles import build_create_article
from app.core.content.articles.application.create_article import CreateArticle


def provide_create_article(
    session: Annotated[Session, Depends(get_session)],
) -> CreateArticle:
    return build_create_article(session)
