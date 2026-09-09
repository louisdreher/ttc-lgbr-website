import pytest

from app.core.content.articles.application.create_article import (
    CreateArticle,
)
from app.core.content.articles.application.dto import CreateArticleCommand
from app.core.content.articles.application.errors import ArticleSlugAlreadyExistsError
from app.core.content.articles.domain.article import (
    Article,
    ArticleStatus,
    ArticleType,
    Visibility,
)


class FakeArticleRepository:
    def __init__(self) -> None:
        self.saved_articles: list[Article] = []
        self.existing_slugs: set[str] = set()

    def slug_exists(self, slug: str) -> bool:
        return slug in self.existing_slugs

    def save(self, article: Article) -> Article:
        article.id = 1
        self.saved_articles.append(article)
        return article


def create_command(
    *,
    author_id: int = 7,
    title: str = "Vereinsmeisterschaft",
    slug: str = "vereinsmeisterschaft-2026",
    teaser: str = "Ein kurzer Teaser.",
    content: str = "Der Artikelinhalt.",
    article_type: ArticleType = ArticleType.NEWS,
    visibility: Visibility = Visibility.PUBLIC,
    event_id: int | None = None,
) -> CreateArticleCommand:
    return CreateArticleCommand(
        author_id=author_id,
        title=title,
        slug=slug,
        teaser=teaser,
        content=content,
        article_type=article_type,
        visibility=visibility,
        event_id=event_id,
    )


def test_create_article_creates_normalized_draft() -> None:
    repository = FakeArticleRepository()
    use_case = CreateArticle(FakeArticleUnitOfWork(repository))

    result = use_case.execute(
        create_command(
            title="  Vereinsmeisterschaft  ",
            slug="  Vereinsmeisterschaft-2026  ",
            teaser="  Ein kurzer Teaser.  ",
            content="  Der Artikelinhalt.  ",
        )
    )

    assert use_case.uow.committed
    assert result.id == 1
    assert result.title == "Vereinsmeisterschaft"
    assert result.slug == "vereinsmeisterschaft-2026"
    assert result.status == ArticleStatus.DRAFT

    assert len(repository.saved_articles) == 1
    saved_article = repository.saved_articles[0]
    assert saved_article.teaser == "Ein kurzer Teaser."
    assert saved_article.content == "Der Artikelinhalt."
    assert saved_article.published_at is None
    assert saved_article.created_at.tzinfo is not None
    assert saved_article.updated_at == saved_article.created_at


def test_create_article_rejects_existing_normalized_slug() -> None:
    repository = FakeArticleRepository()
    repository.existing_slugs.add("vereinsmeisterschaft-2026")
    use_case = CreateArticle(FakeArticleUnitOfWork(repository))

    with pytest.raises(ArticleSlugAlreadyExistsError):
        use_case.execute(create_command(slug="  Vereinsmeisterschaft-2026  "))

    assert not use_case.uow.committed
    assert repository.saved_articles == []


class FakeArticleUnitOfWork:
    def __init__(self, repository):
        self.articles = repository
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def commit(self):
        self.committed = True
