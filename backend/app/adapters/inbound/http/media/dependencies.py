from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from app.adapters.outbound.persistence.database import get_session
from app.bootstrap.media import build_get_image, build_upload_image, configured_media_directory
from app.bootstrap.settings import settings
from app.bootstrap.media import build_get_caption, build_update_caption
from app.bootstrap.media import build_create_gallery
from app.bootstrap.media import build_gallery_opportunities


def provide_gallery_opportunities(session: Annotated[Session, Depends(get_session)]):
    return build_gallery_opportunities(session)


def provide_create_gallery(session: Annotated[Session, Depends(get_session, use_cache=False)]):
    return build_create_gallery(session)


def provide_get_caption(session: Annotated[Session, Depends(get_session)]):
    return build_get_caption(session)


def provide_update_caption(session: Annotated[Session, Depends(get_session, use_cache=False)]):
    return build_update_caption(session)


def provide_get_image(session: Annotated[Session, Depends(get_session)]):
    return build_get_image(
        session, media_directory=configured_media_directory(settings.media_directory)
    )


def provide_upload_image(
    session: Annotated[Session, Depends(get_session, use_cache=False)],
):
    return build_upload_image(
        session,
        media_directory=configured_media_directory(settings.media_directory),
        max_upload_bytes=settings.media_max_upload_bytes,
    )
