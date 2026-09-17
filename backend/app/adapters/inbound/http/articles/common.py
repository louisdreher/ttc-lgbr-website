from contextlib import contextmanager

from app.core.content.articles.application.dto import (
    ArticleActor,
    HiddenEventInput,
    SaveArticleCommand,
)
from app.core.content.articles.application.errors import (
    ArticleAuthorError,
    ArticleConflictError,
    ArticleNotFoundError,
    ArticleSlugAlreadyExistsError,
)
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError


def actor(user=None) -> ArticleActor:
    if user is None:
        return ArticleActor()
    active = user.is_active and not user.is_system
    return ArticleActor(
        user.id,
        active and bool(set(user.roles) & {"ADMIN", "EDITOR", "TEAM_REPORTER"}),
        active and bool(set(user.roles) & {"ADMIN", "EDITOR"}),
        active,
    )


def save_command(request, user, article_id=None):
    values = request.model_dump()
    if values.get("new_event") is not None:
        values["new_event"] = HiddenEventInput(**values["new_event"])
    if "tags" in values:
        values["tags"] = tuple(values["tags"])
    return SaveArticleCommand(actor=actor(user), article_id=article_id, **values)


@contextmanager
def article_errors():
    try:
        yield
    except ArticleNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except ArticleAuthorError as error:
        raise HTTPException(403, str(error)) from error
    except (ArticleConflictError, ArticleSlugAlreadyExistsError) as error:
        raise HTTPException(409, str(error)) from error
    except IntegrityError as error:
        raise HTTPException(
            409, "Beitrag konnte wegen eines Datenkonflikts nicht gespeichert werden."
        ) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
