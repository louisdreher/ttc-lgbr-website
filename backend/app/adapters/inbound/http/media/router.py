import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response
from python_multipart.exceptions import MultipartParseError
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from app.adapters.inbound.http.auth.permissions import require_any_role
from app.adapters.inbound.http.media.dependencies import provide_get_image, provide_upload_image
from app.adapters.inbound.http.auth.dependencies import get_current_user
from app.adapters.inbound.http.media.schemas import UploadedImageResponse
from app.bootstrap.settings import settings
from app.core.content.media.application.dto import GetImageQuery, UploadImageCommand
from app.core.content.media.application.errors import (
    ImageNotFound, InvalidImage, InvalidStorageKey, MediaStorageError,
)
from app.core.users.public import RoleName, UserDetails

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/media", tags=["Admin - Media"])
media_uploader = require_any_role(RoleName.ADMIN, RoleName.EDITOR, RoleName.TEAM_REPORTER)


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
            "properties": {"file": {"type": "string", "format": "binary"}},
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
            request.headers, limited_stream(), max_files=1, max_fields=0
        ).parse()
    except UploadTooLarge as error:
        raise HTTPException(413, "Upload ist zu groß.") from error
    except (MultiPartException, MultipartParseError) as error:
        raise HTTPException(400, "Ungültiger Upload; genau eine Datei ist erforderlich.") from error
    try:
        file = form.get("file")
        if not isinstance(file, UploadFile) or not file.filename or not file.filename.strip():
            raise HTTPException(400, "Eine Datei im Feld 'file' ist erforderlich.")
        data = await file.read(limit + 1)
        if len(data) > limit:
            raise HTTPException(413, "Bilddatei ist zu groß.")
        try:
            return await run_in_threadpool(
                use_case.execute,
                UploadImageCommand(data, file.filename, current_user.id),
            )
        except InvalidImage as error:
            raise HTTPException(422, "Ungültiges, nicht unterstütztes oder zu großes Bild.") from error
        except (MediaStorageError, SQLAlchemyError) as error:
            logger.exception("Media upload persistence failed")
            raise HTTPException(500, "Das Bild konnte nicht gespeichert werden.") from error
    finally:
        await form.close()
