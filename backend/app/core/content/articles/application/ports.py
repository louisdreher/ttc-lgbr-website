from typing import Protocol, Self

from app.core.content.articles.domain.article import Article


class ArticleRepository(Protocol):
    def slug_exists(self, slug: str) -> bool: ...

    def save(self, article: Article) -> Article: ...


class ArticleUnitOfWork(Protocol):
    articles: ArticleRepository

    def __enter__(self) -> Self: ...
    def __exit__(self, exc_type, exc_value, traceback) -> None: ...
    def commit(self) -> None: ...
