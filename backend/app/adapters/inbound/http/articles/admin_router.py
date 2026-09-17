from typing import Annotated, Literal

from app.adapters.inbound.http.articles import dependencies as dep
from app.adapters.inbound.http.articles.common import (
    actor,
    article_errors,
    save_command,
)
from app.adapters.inbound.http.articles.schemas import (
    ArticlePageResponse,
    ArticleResponse,
    ArticleVisibilityRequest,
    CreateArticleRequest,
    CreatedArticleResponse,
    OpportunityPageResponse,
    PreparedArticleResponse,
    SaveArticleRequest,
)
from app.adapters.inbound.http.auth.permissions import require_any_role
from app.core.content.articles.application.dto import (
    EventArticleQuery,
    GetArticleQuery,
    ListArticlesQuery,
    ManageArticleCommand,
    OpportunityQuery,
    PublishArticleCommand,
)
from app.core.content.articles.domain.article import ArticleStatus, ArticleType
from app.core.users.public import RoleName, UserDetails
from fastapi import APIRouter, Depends, Query, Response
from pydantic import AwareDatetime

router = APIRouter(prefix="/api/admin/articles", tags=["Admin - Articles"])
article_editor = require_any_role(
    RoleName.ADMIN, RoleName.EDITOR, RoleName.TEAM_REPORTER
)
editorial_user = require_any_role(RoleName.ADMIN, RoleName.EDITOR)
Writer = Annotated[UserDetails, Depends(article_editor)]
Editor = Annotated[UserDetails, Depends(editorial_user)]


@router.post("", response_model=CreatedArticleResponse, status_code=201)
def create_article_endpoint(
    request: CreateArticleRequest,
    current_user: Writer,
    use_case=Depends(dep.provide_save_article),
    reader=Depends(dep.provide_get_article),
):
    """Compatibility endpoint; /save also supports incomplete drafts."""
    with article_errors():
        article_id = use_case.execute(save_command(request, current_user))
        return reader.execute(
            GetArticleQuery(actor=actor(current_user), article_id=article_id)
        )


@router.get("", response_model=ArticlePageResponse)
def list_articles(
    current_user: Writer,
    scope: Literal["mine", "editorial"] = "mine",
    status: Annotated[list[ArticleStatus] | None, Query()] = None,
    article_type: ArticleType | None = None,
    updated_since: AwareDatetime | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    use_case=Depends(dep.provide_list_articles),
):
    with article_errors():
        return use_case.execute(
            ListArticlesQuery(
                actor=actor(current_user),
                scope=scope,
                statuses=tuple(status or ()),
                article_type=article_type,
                updated_since=updated_since,
                offset=offset,
                limit=limit,
            )
        )


@router.get("/opportunities", response_model=OpportunityPageResponse)
def opportunities(
    current_user: Writer,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    use_case=Depends(dep.provide_opportunities),
):
    with article_errors():
        return use_case.execute(
            OpportunityQuery(actor=actor(current_user), offset=offset, limit=limit)
        )


@router.get("/prepare/{event_id}", response_model=PreparedArticleResponse)
def prepare(
    event_id: int, current_user: Writer, use_case=Depends(dep.provide_prepare_article)
):
    with article_errors():
        return use_case.execute(EventArticleQuery(actor(current_user), event_id))


@router.post("/save", response_model=ArticleResponse)
def save_new(
    request: SaveArticleRequest,
    current_user: Writer,
    use_case=Depends(dep.provide_save_article),
    reader=Depends(dep.provide_get_article),
):
    with article_errors():
        article_id = use_case.execute(save_command(request, current_user))
        return reader.execute(
            GetArticleQuery(actor=actor(current_user), article_id=article_id)
        )


@router.post("/submit", response_model=ArticleResponse)
def submit_new(
    request: SaveArticleRequest,
    current_user: Writer,
    use_case=Depends(dep.provide_submit_article),
    reader=Depends(dep.provide_get_article),
):
    with article_errors():
        article_id = use_case.execute(save_command(request, current_user))
        return reader.execute(
            GetArticleQuery(actor=actor(current_user), article_id=article_id)
        )


@router.get("/{article_id}", response_model=ArticleResponse)
def get_article(
    article_id: int, current_user: Writer, use_case=Depends(dep.provide_get_article)
):
    with article_errors():
        return use_case.execute(
            GetArticleQuery(actor=actor(current_user), article_id=article_id)
        )


@router.put("/{article_id}", response_model=ArticleResponse)
def save_existing(
    article_id: int,
    request: SaveArticleRequest,
    current_user: Writer,
    use_case=Depends(dep.provide_save_article),
    reader=Depends(dep.provide_get_article),
):
    with article_errors():
        use_case.execute(save_command(request, current_user, article_id))
        return reader.execute(
            GetArticleQuery(actor=actor(current_user), article_id=article_id)
        )


@router.post("/{article_id}/submit", response_model=ArticleResponse)
def submit_existing(
    article_id: int,
    request: SaveArticleRequest,
    current_user: Writer,
    use_case=Depends(dep.provide_submit_article),
    reader=Depends(dep.provide_get_article),
):
    with article_errors():
        use_case.execute(save_command(request, current_user, article_id))
        return reader.execute(
            GetArticleQuery(actor=actor(current_user), article_id=article_id)
        )


@router.post("/{article_id}/publish", response_model=ArticleResponse)
def publish(
    article_id: int,
    current_user: Editor,
    use_case=Depends(dep.provide_publish_article),
    reader=Depends(dep.provide_get_article),
):
    with article_errors():
        use_case.execute(PublishArticleCommand(actor(current_user), article_id))
        return reader.execute(
            GetArticleQuery(actor=actor(current_user), article_id=article_id)
        )


@router.patch("/{article_id}/visibility", response_model=ArticleResponse)
def change_visibility(
    article_id: int,
    request: ArticleVisibilityRequest,
    current_user: Editor,
    use_case=Depends(dep.provide_manage_article),
    reader=Depends(dep.provide_get_article),
):
    with article_errors():
        use_case.execute(
            ManageArticleCommand(
                actor(current_user), article_id, "visibility", request.visibility
            )
        )
        return reader.execute(
            GetArticleQuery(actor=actor(current_user), article_id=article_id)
        )


@router.post("/{article_id}/archive", response_model=ArticleResponse)
def archive(
    article_id: int,
    current_user: Editor,
    use_case=Depends(dep.provide_manage_article),
    reader=Depends(dep.provide_get_article),
):
    with article_errors():
        use_case.execute(
            ManageArticleCommand(actor(current_user), article_id, "archive")
        )
        return reader.execute(
            GetArticleQuery(actor=actor(current_user), article_id=article_id)
        )


@router.post("/{article_id}/restore", response_model=ArticleResponse)
def restore(
    article_id: int,
    current_user: Editor,
    use_case=Depends(dep.provide_manage_article),
    reader=Depends(dep.provide_get_article),
):
    with article_errors():
        use_case.execute(
            ManageArticleCommand(actor(current_user), article_id, "restore")
        )
        return reader.execute(
            GetArticleQuery(actor=actor(current_user), article_id=article_id)
        )


@router.delete("/{article_id}", status_code=204)
def delete_article(
    article_id: int, current_user: Editor, use_case=Depends(dep.provide_manage_article)
):
    with article_errors():
        use_case.execute(
            ManageArticleCommand(actor(current_user), article_id, "delete")
        )
        return Response(status_code=204)
