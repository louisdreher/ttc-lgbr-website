from app.auth.permissions import require_any_role
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from backend.app.core.database import get_session
from backend.app.domains.articles.model import Article
from backend.app.domains.articles.schemas import ArticleCreate, ArticleUpdate
from backend.app.domains.users.model import RoleName, User

router = APIRouter(prefix="/api/admin/articles", tags=["Admin - Articles"])


@router.post("/")
def create_article(
    article_data: ArticleCreate,
    session: Session = Depends(get_session),
    user: User = Depends(
        require_any_role(RoleName.ADMIN, RoleName.EDITOR, RoleName.TEAM_REPORTER)
    ),
):
    article = Article.model_validate(article_data)
    session.add(article)
    session.commit()
    session.refresh(article)

    return article


@router.patch("/{article_id}")
def update_article(
    article_id: int,
    article_data: ArticleUpdate,
    session: Session = Depends(get_session),
    user: User = Depends(
        require_any_role(RoleName.ADMIN, RoleName.EDITOR, RoleName.TEAM_REPORTER)
    ),
):
    article = session.get(Article, article_id)

    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    update_data = article_data.model_dump(exclude_unset=True)

    article.sqlmodel_update(update_data)

    session.add(article)
    session.commit()
    session.refresh(article)

    return article


@router.delete("/{article_id}")
def delete_article(
    article_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(
        require_any_role(RoleName.ADMIN, RoleName.EDITOR, RoleName.TEAM_REPORTER)
    ),
):
    article = session.get(Article, article_id)

    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    session.delete(article)
    session.commit()

    return {"ok": True}
