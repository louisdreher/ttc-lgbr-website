import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from python_multipart.exceptions import MultipartParseError
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from app.adapters.inbound.http.auth.permissions import require_any_role
from app.adapters.inbound.http.media.dependencies import provide_get_image, provide_upload_image
from app.adapters.inbound.http.auth.dependencies import get_current_user
from app.adapters.inbound.http.media.schemas import UploadedImageResponse
from app.adapters.inbound.http.media.schemas import CaptionRequest, CaptionResponse
from app.adapters.inbound.http.media.dependencies import provide_get_caption, provide_update_caption
from app.core.content.media.application.dto import UpdateCaptionCommand
from app.core.content.media.domain.asset import InvalidCaption
from app.bootstrap.settings import settings
from app.core.content.media.application.dto import GetImageQuery, UploadImageCommand
from app.core.content.media.application.errors import (
    ImageNotFound, InvalidImage, InvalidStorageKey, MediaStorageError,
)
from app.core.users.public import RoleName, UserDetails
from app.adapters.inbound.http.media.dependencies import provide_create_gallery
from app.adapters.inbound.http.media.schemas import CreateGalleryRequest, CreatedGalleryResponse
from app.core.content.media.application.dto import CreateGalleryCommand, GalleryNewEvent
from app.core.content.media.application.errors import GalleryAccessDenied, EventGalleryAlreadyExists
from app.core.content.media.domain.gallery import GalleryError
from app.adapters.inbound.http.media.dependencies import provide_gallery_opportunities
from app.adapters.inbound.http.media.schemas import GalleryOpportunityPageResponse
from app.core.content.media.application.dto import GalleryOpportunitiesQuery

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/media", tags=["Admin - Media"])
media_uploader = require_any_role(RoleName.ADMIN, RoleName.EDITOR, RoleName.TEAM_REPORTER)


@router.get("/galleries/opportunities", response_model=GalleryOpportunityPageResponse)
def gallery_opportunities(
    current_user: Annotated[UserDetails, Depends(media_uploader)],
    response: Response,
    group: Literal["other_events", "team_matches"] = "other_events",
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    use_case=Depends(provide_gallery_opportunities),
):
    response.headers["Cache-Control"] = "private, no-store"
    try:
        return use_case.execute(GalleryOpportunitiesQuery(
            user_id=current_user.id, can_upload=True, group=group, offset=offset, limit=limit,
        ))
    except GalleryAccessDenied as error:
        raise HTTPException(403, str(error)) from error
    except GalleryError as error:
        raise HTTPException(422, str(error)) from error
    except SQLAlchemyError as error:
        logger.exception("Could not read gallery opportunities")
        raise HTTPException(500, "Galerieauswahl konnte nicht geladen werden.") from error


@router.post("/galleries", response_model=CreatedGalleryResponse, status_code=201)
def create_gallery(
    request: CreateGalleryRequest,
    current_user: Annotated[UserDetails, Depends(media_uploader)],
    use_case=Depends(provide_create_gallery),
):
    try:
        return use_case.execute(CreateGalleryCommand(
            title=request.title, event_id=request.event_id,
            gallery_date=request.gallery_date, show_date=request.show_date,
            media_ids=tuple(request.media_ids), user_id=current_user.id,
            can_upload=True,
            can_manage_media=bool({"ADMIN", "EDITOR"}.intersection(current_user.roles)),
            new_event=GalleryNewEvent(**request.new_event.model_dump()) if request.new_event else None,
        ))
    except GalleryAccessDenied as error:
        raise HTTPException(403, str(error)) from error
    except EventGalleryAlreadyExists as error:
        raise HTTPException(409, str(error)) from error
    except ImageNotFound as error:
        raise HTTPException(404, "Bild nicht gefunden.") from error
    except GalleryError as error:
        raise HTTPException(422, str(error)) from error
    except SQLAlchemyError as error:
        logger.exception("Could not create gallery")
        raise HTTPException(500, "Galerie konnte nicht gespeichert werden.") from error


@router.get("/images/{media_id}/caption", response_model=CaptionResponse)
def get_caption(
    media_id: Annotated[int, Path(gt=0)],
    current_user: Annotated[UserDetails, Depends(get_current_user)],
    response: Response,
    use_case=Depends(provide_get_caption),
):
    response.headers["Cache-Control"] = "private, no-store"
    try:
        caption = use_case.execute(GetImageQuery(
            media_id, current_user.id, bool({"ADMIN", "EDITOR"}.intersection(current_user.roles))
        ))
        return CaptionResponse(caption=caption)
    except ImageNotFound as error:
        raise HTTPException(404, "Bild nicht gefunden.") from error
    except SQLAlchemyError as error:
        logger.exception("Could not read image caption")
        raise HTTPException(500, "Bildunterschrift konnte nicht geladen werden.") from error


@router.patch("/images/{media_id}/caption", response_model=CaptionResponse)
def update_caption(
    media_id: Annotated[int, Path(gt=0)],
    request: CaptionRequest,
    current_user: Annotated[UserDetails, Depends(media_uploader)],
    use_case=Depends(provide_update_caption),
):
    try:
        caption = use_case.execute(UpdateCaptionCommand(
            media_id, current_user.id, request.caption,
            bool({"ADMIN", "EDITOR"}.intersection(current_user.roles)),
        ))
        return CaptionResponse(caption=caption)
    except ImageNotFound as error:
        raise HTTPException(404, "Bild nicht gefunden.") from error
    except InvalidCaption as error:
        raise HTTPException(422, str(error)) from error
    except SQLAlchemyError as error:
        logger.exception("Could not update image caption")
        raise HTTPException(500, "Bildunterschrift konnte nicht gespeichert werden.") from error


@router.get(
    "/images/{media_id}", response_class=Response,
    responses={200: {"content": {"image/webp": {"schema": {
        "type": "string", "format": "binary",
    }}}}},
)
def get_image(
    media_id: Annotated[int, Path(gt=0)],
    current_user: Annotated[UserDetails, Depends(get_current_user)],
    use_case=Depends(provide_get_image),
):
    headers = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}
    try:
        data = use_case.execute(GetImageQuery(
            media_id=media_id,
            user_id=current_user.id,
            can_manage_media=bool({"ADMIN", "EDITOR"}.intersection(current_user.roles)),
        ))
    except ImageNotFound as error:
        raise HTTPException(404, "Bild nicht gefunden.", headers=headers) from error
    except (MediaStorageError, InvalidStorageKey, SQLAlchemyError) as error:
        logger.exception("Media retrieval failed for asset %s", media_id)
        raise HTTPException(500, "Das Bild konnte nicht geladen werden.", headers=headers) from error
    return Response(data, media_type="image/webp", headers=headers)


class UploadTooLarge(MultiPartException):
    pass


@router.post(
    "/images", status_code=201, response_model=UploadedImageResponse,
    openapi_extra={"requestBody": {"required": True, "content": {
        "multipart/form-data": {"schema": {
            "type": "object", "required": ["file"],
            "properties": {
                "file": {"type": "string", "format": "binary"},
                "caption": {"type": "string", "maxLength": 1000},
            },
        }},
    }}},
)
async def upload_image(
    request: Request,
    current_user: Annotated[UserDetails, Depends(media_uploader)],
    use_case=Depends(provide_upload_image),
):
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "multipart/form-data":
        raise HTTPException(415, "Erwartet wird multipart/form-data.")
    limit = settings.media_max_upload_bytes

    async def limited_stream():
        received = 0
        async for chunk in request.stream():
            received += len(chunk)
            # Allow bounded multipart headers in addition to the image bytes.
            if received > limit + 64 * 1024:
                raise UploadTooLarge("Upload ist zu groß.")
            yield chunk

    try:
        form = await MultiPartParser(
            request.headers, limited_stream(), max_files=1, max_fields=1
        ).parse()
    except UploadTooLarge as error:
        raise HTTPException(413, "Upload ist zu groß.") from error
    except (MultiPartException, MultipartParseError) as error:
        raise HTTPException(400, "Ungültiger Upload; genau eine Datei ist erforderlich.") from error
    try:
        if any(key not in {"file", "caption"} for key in form):
            raise HTTPException(400, "Unbekanntes Upload-Feld.")
        caption = form.get("caption")
        if caption is not None and not isinstance(caption, str):
            raise HTTPException(400, "Die Bildunterschrift muss Text sein.")
        file = form.get("file")
        if not isinstance(file, UploadFile) or not file.filename or not file.filename.strip():
            raise HTTPException(400, "Eine Datei im Feld 'file' ist erforderlich.")
        data = await file.read(limit + 1)
        if len(data) > limit:
            raise HTTPException(413, "Bilddatei ist zu groß.")
        try:
            return await run_in_threadpool(
                use_case.execute,
                UploadImageCommand(data, file.filename, current_user.id, caption),
            )
        except InvalidCaption as error:
            raise HTTPException(422, str(error)) from error
        except InvalidImage as error:
            raise HTTPException(422, "Ungültiges, nicht unterstütztes oder zu großes Bild.") from error
        except (MediaStorageError, SQLAlchemyError) as error:
            logger.exception("Media upload persistence failed")
            raise HTTPException(500, "Das Bild konnte nicht gespeichert werden.") from error
    finally:
        await form.close()
