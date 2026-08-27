from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from backend.app.core.database import get_session
from backend.app.domains.articles.model import Article

router = APIRouter(prefix="/api/articles", tags=["Articles"])


@router.get("/")
def get_articles(session: Session = Depends(get_session)):

    statement = select(Article).where(Article.published == True)

    articles = session.exec(statement).all()
    return articles


@router.get("/{slug}")
def get_article(slug: str, session: Session = Depends(get_session)):

    statement = select(Article).where(Article.slug == slug, Article.published == True)

    article = session.exec(statement).first()

    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    return article
