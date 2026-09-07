from app.core.content.articles.domain.article import (
    Article,
)
from app.core.content.articles.domain.article import (
    ArticleStatus as DomainArticleStatus,
)
from app.core.content.articles.domain.article import (
    ArticleType as DomainArticleType,
)
from app.core.content.articles.domain.article import (
    Visibility as DomainVisibility,
)
from app.core.content.articles.model import (
    Article as ArticleRecord,
)
from app.core.content.articles.model import (
    ArticleStatus as PersistenceArticleStatus,
)
from app.core.content.articles.model import (
    ArticleType as PersistenceArticleType,
)
from app.core.content.types import Visibility as PersistenceVisibility
from sqlmodel import Session, select


class SQLModelArticleRepository:
    def __init__(self, session: Session):
        self.session = session

    def slug_exists(self, slug: str) -> bool:
        statement = select(ArticleRecord).where(ArticleRecord.slug == slug)
        return self.session.exec(statement).first() is not None

    def save(self, article: Article) -> Article:
        record = self._to_record(article)

        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)

        return self._to_domain(record)

    @staticmethod
    def _to_record(article: Article) -> ArticleRecord:
        return ArticleRecord(
            id=article.id,
            author_id=article.author_id,
            title=article.title,
            slug=article.slug,
            teaser=article.teaser,
            content=article.content,
            article_type=PersistenceArticleType(article.article_type.value),
            visibility=PersistenceVisibility(article.visibility.value),
            status=PersistenceArticleStatus(article.status.value),
            event_id=article.event_id,
            published_at=article.published_at,
            created_at=article.created_at,
            updated_at=article.updated_at,
        )

    @staticmethod
    def _to_domain(record: ArticleRecord) -> Article:
        return Article(
            id=record.id,
            author_id=record.author_id,
            title=record.title,
            slug=record.slug,
            teaser=record.teaser,
            content=record.content,
            article_type=DomainArticleType(record.article_type.value),
            visibility=DomainVisibility(record.visibility.value),
            status=DomainArticleStatus(record.status.value),
            event_id=record.event_id,
            published_at=record.published_at,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
