from typing import Annotated

from app.adapters.inbound.http.articles import dependencies as dep
from app.adapters.inbound.http.articles.common import actor, article_errors
from app.adapters.inbound.http.articles.schemas import (
    PublicArticlePageResponse,
    PublicArticleResponse,
)
from app.adapters.inbound.http.auth.dependencies import get_current_user
from app.core.content.articles.application.dto import GetArticleQuery, ListArticlesQuery
from app.core.content.articles.domain.article import ArticleType
from app.core.users.public import UserDetails
from fastapi import APIRouter, Depends, Query

router = APIRouter(prefix="/api/articles", tags=["Articles"])
member_router = APIRouter(prefix="/api/intern/articles", tags=["Member articles"])


@router.get("", response_model=PublicArticlePageResponse)
def list_public(
    article_type: ArticleType | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    use_case=Depends(dep.provide_list_articles),
):
    with article_errors():
        return use_case.execute(
            ListArticlesQuery(
                actor=actor(),
                scope="public",
                article_type=article_type,
                offset=offset,
                limit=limit,
            )
        )


@member_router.get("", response_model=PublicArticlePageResponse)
def list_members(
    user: Annotated[UserDetails, Depends(get_current_user)],
    article_type: ArticleType | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    use_case=Depends(dep.provide_list_articles),
):
    with article_errors():
        return use_case.execute(
            ListArticlesQuery(
                actor=actor(user),
                scope="members",
                article_type=article_type,
                offset=offset,
                limit=limit,
            )
        )


@member_router.get("/{slug}", response_model=PublicArticleResponse)
def get_member_article(
    slug: str,
    user: Annotated[UserDetails, Depends(get_current_user)],
    use_case=Depends(dep.provide_get_article),
):
    with article_errors():
        return use_case.execute(
            GetArticleQuery(actor=actor(user), scope="members", slug=slug)
        )


@router.get("/{slug}", response_model=PublicArticleResponse)
def get_public_article(slug: str, use_case=Depends(dep.provide_get_article)):
    with article_errors():
        return use_case.execute(
            GetArticleQuery(actor=actor(), scope="public", slug=slug)
        )
