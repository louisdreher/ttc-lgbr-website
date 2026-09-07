from typing import Protocol

from app.core.content.articles.domain.article import Article


class ArticleRepository(Protocol):
    def slug_exists(self, slug: str) -> bool: ...

    def save(self, article: Article) -> Article: ...
