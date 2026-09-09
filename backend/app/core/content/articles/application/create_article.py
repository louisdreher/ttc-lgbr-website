from app.core.content.articles.application.dto import (
    CreateArticleCommand,
    CreatedArticle,
)
from app.core.content.articles.application.errors import (
    ArticleSlugAlreadyExistsError,
)
from app.core.content.articles.application.ports import (
    ArticleUnitOfWork,
)
from app.core.content.articles.domain.article import (
    Article,
)


class CreateArticle:
    def __init__(self, uow: ArticleUnitOfWork):
        self.uow = uow

    def execute(
        self,
        command: CreateArticleCommand,
    ) -> CreatedArticle:
        with self.uow:
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

            if self.uow.articles.slug_exists(article.slug):
                raise ArticleSlugAlreadyExistsError(article.slug)

            saved_article = self.uow.articles.save(article)

            if saved_article.id is None:
                raise RuntimeError("Der gespeicherte Artikel besitzt keine ID.")

            result = CreatedArticle(
                id=saved_article.id,
                title=saved_article.title,
                slug=saved_article.slug,
                status=saved_article.status,
            )
            self.uow.commit()
            return result
