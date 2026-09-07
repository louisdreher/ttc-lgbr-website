from dataclasses import dataclass

from app.core.content.articles.application.errors import (
    ArticleSlugAlreadyExistsError,
)
from app.core.content.articles.application.ports import (
    ArticleRepository,
)
from app.core.content.articles.domain.article import (
    Article,
    ArticleStatus,
    ArticleType,
    Visibility,
)


@dataclass(frozen=True)
class CreateArticleCommand:
    author_id: int
    title: str
    slug: str
    teaser: str
    content: str
    article_type: ArticleType
    visibility: Visibility
    event_id: int | None = None


@dataclass(frozen=True)
class CreatedArticle:
    id: int
    title: str
    slug: str
    status: ArticleStatus


class CreateArticle:
    def __init__(self, articles: ArticleRepository):
        self.articles = articles

    def create(
        self,
        command: CreateArticleCommand,
    ) -> CreatedArticle:
        article = Article.create_draft(
            author_id=command.author_id,
            title=command.title,
            slug=command.slug,
            teaser=command.teaser,
            content=command.content,
            article_type=command.article_type,
            visibility=command.visibility,
            event_id=command.event_id,
        )

        if self.articles.slug_exists(article.slug):
            raise ArticleSlugAlreadyExistsError(article.slug)

        saved_article = self.articles.save(article)

        if saved_article.id is None:
            raise RuntimeError("Der gespeicherte Artikel besitzt keine ID.")

        return CreatedArticle(
            id=saved_article.id,
            title=saved_article.title,
            slug=saved_article.slug,
            status=saved_article.status,
        )
