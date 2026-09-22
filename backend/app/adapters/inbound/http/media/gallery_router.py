from app.core.content.media.application.dto import GetEventGalleryQuery
from app.adapters.inbound.http.media.schemas import GalleryImageCaptionResponse
import logging
from contextlib import contextmanager
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy.exc import SQLAlchemyError
from app.adapters.inbound.http.auth.permissions import require_any_role
from app.adapters.inbound.http.media import dependencies as dep
from app.adapters.inbound.http.media.schemas import GalleryPageResponse, GalleryDetailsResponse, UpdateGalleryRequest
from app.core.content.media.application.dto import GetGalleryQuery, ListGalleriesQuery, UpdateGalleryCommand
from app.core.content.media.application.errors import GalleryNotFound, GalleryAccessDenied, GalleryConflict, ImageNotFound, MediaStorageError, InvalidStorageKey
from app.core.content.media.domain.gallery import GalleryError
from app.core.users.public import RoleName, UserDetails

router = APIRouter(prefix="/api/admin/media/galleries", tags=["Admin - Media"])
User = Annotated[UserDetails, Depends(require_any_role(RoleName.ADMIN, RoleName.EDITOR, RoleName.TEAM_REPORTER))]
Id = Annotated[int, Path(gt=0)]
logger = logging.getLogger(__name__)


def access(user: UserDetails):
    return dict(user_id=user.id, can_upload=True, can_manage_media=bool({"ADMIN", "EDITOR"}.intersection(user.roles)))


@contextmanager
def gallery_errors():
    try:
        yield
    except (GalleryNotFound, ImageNotFound) as error:
        raise HTTPException(404, "Galerie oder Bild nicht gefunden.") from error
    except GalleryAccessDenied as error:
        raise HTTPException(403, str(error)) from error
    except GalleryConflict as error:
        raise HTTPException(409, str(error)) from error
    except GalleryError as error:
        raise HTTPException(422, str(error)) from error
    except (SQLAlchemyError, MediaStorageError, InvalidStorageKey) as error:
        logger.exception("Gallery operation failed")
        raise HTTPException(500, "Die Galerie konnte nicht verarbeitet werden.") from error


@router.get("", response_model=GalleryPageResponse)
def list_galleries(user: User, response: Response, year: int | None = Query(None, ge=1, le=9999),
                   offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
                   use_case=Depends(dep.provide_list_galleries)):
    response.headers["Cache-Control"] = "private, no-store"
    with gallery_errors():
        return use_case.execute(ListGalleriesQuery(**access(user), year=year, offset=offset, limit=limit))


@router.get("/events/{event_id}", response_model=GalleryDetailsResponse | None)
def event_gallery(event_id: Id, user: User, response: Response, use_case=Depends(dep.provide_event_gallery)):
    response.headers["Cache-Control"] = "private, no-store"
    with gallery_errors():
        return use_case.execute(GetEventGalleryQuery(event_id=event_id, **access(user)))


@router.get("/events/{event_id}/images/{media_id}", response_class=Response)
def event_gallery_image(event_id: Id, media_id: Id, user: User, use_case=Depends(dep.provide_event_gallery_image)):
    with gallery_errors():
        data = use_case.execute(GetEventGalleryQuery(event_id=event_id, **access(user)), media_id)
    return Response(data, media_type="image/webp", headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/events/{event_id}/images/{media_id}/caption", response_model=GalleryImageCaptionResponse)
def event_gallery_caption(event_id: Id, media_id: Id, user: User, response: Response, use_case=Depends(dep.provide_event_gallery_image)):
    response.headers["Cache-Control"] = "private, no-store"
    with gallery_errors():
        return use_case.caption(GetEventGalleryQuery(event_id=event_id, **access(user)), media_id)


@router.get("/{gallery_id}", response_model=GalleryDetailsResponse)
def get_gallery(gallery_id: Id, user: User, response: Response, use_case=Depends(dep.provide_get_gallery)):
    response.headers["Cache-Control"] = "private, no-store"
    with gallery_errors():
        return use_case.execute(GetGalleryQuery(gallery_id=gallery_id, **access(user)))


@router.put("/{gallery_id}", status_code=204)
def update_gallery(gallery_id: Id, request: UpdateGalleryRequest, user: User, use_case=Depends(dep.provide_update_gallery)):
    with gallery_errors():
        values = request.model_dump()
        values["media_ids"] = tuple(values["media_ids"])
        use_case.execute(UpdateGalleryCommand(gallery_id=gallery_id, **access(user), **values))
    return Response(status_code=204)


@router.get("/{gallery_id}/images/{media_id}", response_class=Response)
def gallery_image(gallery_id: Id, media_id: Id, user: User, use_case=Depends(dep.provide_gallery_image)):
    with gallery_errors():
        data = use_case.execute(GetGalleryQuery(gallery_id=gallery_id, **access(user)), media_id)
    return Response(data, media_type="image/webp", headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})
