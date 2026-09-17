from typing import Annotated

from app.adapters.outbound.persistence.database import get_session
from app.bootstrap import articles as wiring
from app.bootstrap.articles import build_create_article
from app.core.content.articles.application.create_article import CreateArticle
from fastapi import Depends
from sqlmodel import Session


def provide_create_article(
    session: Annotated[Session, Depends(get_session)],
) -> CreateArticle:
    return build_create_article(session)


def provide_save_article(session: Annotated[Session, Depends(get_session)]):
    return wiring.build_save_article(session)


def provide_submit_article(session: Annotated[Session, Depends(get_session)]):
    return wiring.build_save_article(session, submit=True)


def provide_publish_article(session: Annotated[Session, Depends(get_session)]):
    return wiring.build_publish_article(session)


def provide_manage_article(session: Annotated[Session, Depends(get_session)]):
    return wiring.build_manage_article(session)


def provide_list_articles(session: Annotated[Session, Depends(get_session)]):
    return wiring.build_list_articles(session)


def provide_get_article(session: Annotated[Session, Depends(get_session)]):
    return wiring.build_get_article(session)


def provide_opportunities(session: Annotated[Session, Depends(get_session)]):
    return wiring.build_article_opportunities(session)


def provide_prepare_article(session: Annotated[Session, Depends(get_session)]):
    return wiring.build_prepare_article(session)
