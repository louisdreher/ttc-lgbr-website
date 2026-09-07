from app.adapters.inbound.http.articles.dependencies import get_create_article
from app.adapters.inbound.http.articles.schemas import (
    CreateArticleRequest,
    CreatedArticleResponse,
)
from app.core.auth.permissions import require_any_role
from app.core.content.articles.application.create_article import (
    CreateArticle,
    CreateArticleCommand,
)
from app.core.content.articles.application.errors import (
    ArticleSlugAlreadyExistsError,
)
from app.core.content.articles.domain.errors import ArticleDomainError
from app.core.users.model import RoleName, User
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(
    prefix="/api/admin/articles",
    tags=["Admin - Articles"],
)
article_editor = require_any_role(RoleName.ADMIN, RoleName.EDITOR)


@router.post(
    "",
    response_model=CreatedArticleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_article_endpoint(
    request: CreateArticleRequest,
    current_user: User = Depends(article_editor),
    use_case: CreateArticle = Depends(get_create_article),
) -> CreatedArticleResponse:
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Der angemeldete Benutzer besitzt keine ID.",
        )

    command = CreateArticleCommand(
        author_id=current_user.id,
        title=request.title,
        slug=request.slug,
        teaser=request.teaser,
        content=request.content,
        article_type=request.article_type,
        visibility=request.visibility,
        event_id=request.event_id,
    )

    try:
        result = use_case.create(command)
    except ArticleSlugAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except ArticleDomainError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error

    return CreatedArticleResponse(
        id=result.id,
        title=result.title,
        slug=result.slug,
        status=result.status,
    )
