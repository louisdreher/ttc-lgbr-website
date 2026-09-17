from app.adapters.outbound.persistence.articles.models import Article, ArticleTag, Tag
from app.adapters.outbound.persistence.events.models import Event
from app.core.content.articles.application.dto import (
    ArticleDetails,
    ArticleOpportunity,
    ArticlePage,
    ListArticlesQuery,
    OpportunityPage,
    OpportunityQuery,
)
from app.core.content.articles.domain.article import (
    ArticleStatus,
    ArticleType,
    Visibility,
)
from app.core.users.public import UserReader
from sqlalchemy import and_, func, or_
from sqlmodel import Session, select


class SqlArticleReader:
    def __init__(self, session: Session, users: UserReader):
        self.session, self.users = session, users

    def _details(self, rows) -> tuple[ArticleDetails, ...]:
        system_id = self.users.get_system_author_id()
        names = self.users.get_names({row.author_id for row in rows})
        ids = [row.id for row in rows]
        tags = {key: [] for key in ids}
        if ids:
            for article_id, slug in self.session.exec(
                select(ArticleTag.article_id, Tag.slug)
                .join(Tag, Tag.id == ArticleTag.tag_id)
                .where(ArticleTag.article_id.in_(ids))
                .order_by(Tag.slug)
            ).all():
                tags[article_id].append(slug)
        return tuple(
            ArticleDetails(
                id=row.id,
                author_id=row.author_id,
                author_name=names.get(row.author_id, ""),
                title=row.title,
                slug=row.slug,
                teaser=row.teaser,
                content=row.content,
                article_type=ArticleType(row.article_type),
                visibility=Visibility(row.visibility),
                status=ArticleStatus(row.status),
                event_id=row.event_id,
                published_at=row.published_at,
                updated_at=row.updated_at,
                tags=tuple(tags[row.id]),
                cover_image_id=row.cover_image_id,
                system_authored=row.author_id == system_id,
                generated=row.generation_key is not None,
            )
            for row in rows
        )

    def get(self, *, article_id=None, slug=None, event_id=None):
        query = select(Article)
        if article_id is not None:
            query = query.where(Article.id == article_id)
        elif slug is not None:
            query = query.where(Article.slug == slug)
        elif event_id is not None:
            query = query.where(Article.event_id == event_id)
        else:
            return None
        row = self.session.exec(query).first()
        return self._details([row])[0] if row else None

    def list(self, query: ListArticlesQuery) -> ArticlePage:
        conditions = []
        if query.scope == "mine":
            conditions.append(Article.author_id == query.actor.user_id)
        elif query.scope in ("public", "members"):
            conditions.append(Article.status == ArticleStatus.PUBLISHED)
            allowed = [Visibility.PUBLIC]
            if query.scope == "members":
                allowed.append(Visibility.MEMBERS_ONLY)
            conditions.append(Article.visibility.in_(allowed))
        if query.statuses:
            conditions.append(Article.status.in_(query.statuses))
        if query.article_type is not None:
            conditions.append(Article.article_type == query.article_type)
        if query.updated_since is not None:
            conditions.append(Article.updated_at >= query.updated_since)
        total = self.session.exec(
            select(func.count()).select_from(Article).where(*conditions)
        ).one()
        sort = (
            Article.published_at
            if query.scope in ("public", "members")
            else Article.updated_at
        )
        rows = self.session.exec(
            select(Article)
            .where(*conditions)
            .order_by(sort.desc(), Article.id.desc())
            .offset(query.offset)
            .limit(query.limit)
        ).all()
        return ArticlePage(self._details(rows), total, query.offset, query.limit)

    def opportunities(self, query: OpportunityQuery) -> OpportunityPage:
        system_id = self.users.get_system_author_id()
        eligible = or_(
            Article.id.is_(None),
            and_(Article.author_id == system_id, Article.status == ArticleStatus.DRAFT),
        )
        base = (
            select(Event, Article.id)
            .outerjoin(Article, Article.event_id == Event.id)
            .where(eligible)
        )
        total = self.session.exec(
            select(func.count()).select_from(base.subquery())
        ).one()
        rows = self.session.exec(
            base.order_by(Event.starts_at.desc(), Event.id.desc())
            .offset(query.offset)
            .limit(query.limit)
        ).all()
        items = [
            ArticleOpportunity(e.id, e.title, e.starts_at, e.team_match_id, aid)
            for e, aid in rows
        ]
        return OpportunityPage(
            tuple(x for x in items if x.team_match_id is not None),
            tuple(x for x in items if x.team_match_id is None),
            total,
            query.offset,
            query.limit,
        )
