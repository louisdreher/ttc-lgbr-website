"""Article permissions, independent of HTTP and concrete role names."""

from app.core.content.articles.application.dto import ArticleActor, ArticleDetails
from app.core.content.articles.application.errors import ArticleAuthorError
from app.core.content.articles.domain.article import ArticleStatus


def require_writer(actor: ArticleActor) -> None:
    if actor.user_id is None or not actor.can_write:
        raise ArticleAuthorError("Keine Schreibberechtigung.")


def require_editor(actor: ArticleActor) -> None:
    require_writer(actor)
    if not actor.can_edit_all:
        raise ArticleAuthorError("Redaktionsrechte erforderlich.")


def actions(actor: ArticleActor, article: ArticleDetails) -> tuple[str, ...]:
    if not actor.can_write:
        return ()
    if article.status == ArticleStatus.ARCHIVED:
        return ("visibility", "restore", "delete") if actor.can_edit_all else ()
    unpublished = article.status in (ArticleStatus.DRAFT, ArticleStatus.IN_REVIEW)
    own = article.author_id == actor.user_id
    if not actor.can_edit_all and not (
        unpublished and (own or article.system_authored)
    ):
        return ()
    result = ["save"]
    if actor.can_edit_all:
        result.extend(("visibility", "archive", "delete"))
    if unpublished:
        result.append("submit")
        if actor.can_edit_all:
            result.append("publish")
    return tuple(result)
