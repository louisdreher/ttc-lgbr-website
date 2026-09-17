from app.adapters.outbound.persistence.articles.models import (
    Article as ArticleRecord,
)
from app.adapters.outbound.persistence.articles.models import (
    ArticleStatus as PersistenceArticleStatus,
)
from app.adapters.outbound.persistence.articles.models import ArticleTag, Tag
from app.adapters.outbound.persistence.articles.models import (
    ArticleType as PersistenceArticleType,
)
from app.adapters.outbound.persistence.events.models import Event
from app.adapters.outbound.persistence.media.models import MediaAsset
from app.core.content.articles.application.errors import ArticleNotFoundError
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
from app.core.content.articles.domain.errors import ArticleDomainError
from app.core.content.types import Visibility as PersistenceVisibility
from sqlalchemy import delete, or_, text
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
            record.sqlmodel_update(values.model_dump())

        self.session.add(record)
        self.session.flush()

        self.session.exec(delete(ArticleTag).where(ArticleTag.article_id == record.id))
        for slug in sorted(article.tags):
            # Serialize shared tag creation across articles.
            if self.session.get_bind().dialect.name == "postgresql":
                self.session.execute(
                    text("SELECT pg_advisory_xact_lock(72106, hashtext(:slug))"),
                    {"slug": slug},
                )
            tag = self.session.exec(select(Tag).where(Tag.slug == slug)).first()
            if tag is None:
                tag = Tag(name=slug, slug=slug)
                self.session.add(tag)
                self.session.flush()
            self.session.add(ArticleTag(article_id=record.id, tag_id=tag.id))
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
            # A transaction-scoped lock also covers a not-yet-existing article.
            self.session.execute(
                text("SELECT pg_advisory_xact_lock(72104, :match_id)"),
                {"match_id": team_match_id},
            )

    def lock_event(self, event_id: int) -> None:
        row = self.session.exec(
            select(Event).where(Event.id == event_id).with_for_update()
        ).first()
        if row is None:
            raise ArticleNotFoundError("Event nicht gefunden.")

    def find_by_event(self, event_id: int) -> Article | None:
        row = self.session.exec(
            select(ArticleRecord).where(ArticleRecord.event_id == event_id)
        ).first()
        return self._to_domain(row) if row else None

    def validate_cover(self, cover_image_id: int | None) -> None:
        if (
            cover_image_id is not None
            and self.session.get(MediaAsset, cover_image_id) is None
        ):
            raise ArticleDomainError("Titelbild nicht gefunden.")

    def delete(self, article: Article) -> None:
        self.session.exec(delete(ArticleTag).where(ArticleTag.article_id == article.id))
        self.session.exec(delete(ArticleRecord).where(ArticleRecord.id == article.id))
        self.session.flush()

    def find_match_report(self, key: str, event_id: int | None) -> Article | None:
        condition = ArticleRecord.generation_key == key
        if event_id is not None:
            condition = or_(
                condition,
                ArticleRecord.event_id == event_id,
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
            cover_image_id=article.cover_image_id,
        )

    def _to_domain(self, record: ArticleRecord) -> Article:
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
            cover_image_id=record.cover_image_id,
            tags=list(
                self.session.exec(
                    select(Tag.slug)
                    .join(ArticleTag, ArticleTag.tag_id == Tag.id)
                    .where(ArticleTag.article_id == record.id)
                    .order_by(Tag.slug)
                ).all()
            ),
        )
