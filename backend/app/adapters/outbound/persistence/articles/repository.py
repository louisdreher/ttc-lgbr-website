from app.adapters.outbound.persistence.articles.models import (
    Article as ArticleRecord,
)
from app.adapters.outbound.persistence.articles.models import (
    ArticleStatus as PersistenceArticleStatus,
)
from app.adapters.outbound.persistence.articles.models import (
    ArticleType as PersistenceArticleType,
)
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
from app.core.content.types import Visibility as PersistenceVisibility
from sqlalchemy import or_, text
from sqlmodel import Session, select


class SQLModelArticleRepository:
    def __init__(self, session: Session):
        self.session = session

    def slug_exists(self, slug: str) -> bool:
        statement = select(ArticleRecord).where(ArticleRecord.slug == slug)
        return self.session.exec(statement).first() is not None

    def save(self, article: Article) -> Article:
        values = self._to_record(article)
        record = (
            self.session.get(ArticleRecord, article.id)
            if article.id is not None
            else None
        )
        if record is None:
            record = values
        else:
            # Preserve cover images and tags, which are not part of this domain operation.
            record.sqlmodel_update(values.model_dump(exclude={"cover_image_id"}))

        self.session.add(record)
        self.session.flush()

        return self._to_domain(record)

    def get(self, article_id: int, *, for_update: bool = False) -> Article | None:
        query = select(ArticleRecord).where(ArticleRecord.id == article_id)
        if for_update:
            query = query.with_for_update().execution_options(populate_existing=True)
        row = self.session.exec(query).first()
        return self._to_domain(row) if row is not None else None

    def lock_generation(self, team_match_id: int) -> None:
        if self.session.get_bind().dialect.name == "postgresql":
            # A transaction-scoped namespace lock also covers a not-yet-existing article.
            self.session.execute(
                text("SELECT pg_advisory_xact_lock(72104, :match_id)"),
                {"match_id": team_match_id},
            )

    def find_match_report(self, key: str, event_id: int | None) -> Article | None:
        condition = ArticleRecord.generation_key == key
        if event_id is not None:
            condition = or_(
                condition,
                (ArticleRecord.event_id == event_id)
                & (ArticleRecord.article_type == PersistenceArticleType.MATCH_REPORT),
            )
        row = self.session.exec(
            select(ArticleRecord).where(condition).order_by(ArticleRecord.id)
        ).first()
        return self._to_domain(row) if row is not None else None

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
            generation_key=article.generation_key,
            generation_method=article.generation_method,
            generated_at=article.generated_at,
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
            generation_key=record.generation_key,
            generation_method=record.generation_method,
            generated_at=record.generated_at,
        )
