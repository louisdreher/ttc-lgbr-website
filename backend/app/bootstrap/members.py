from collections.abc import Callable

from sqlmodel import Session

from app.adapters.outbound.persistence.database import engine
from app.adapters.outbound.persistence.members.player_images import SqlPlayerImageReader
from app.core.members.application.queries import GetPlayerImages
from app.core.members.application.commands import AssignPlayerImage
from app.adapters.outbound.persistence.members.player_image_unit_of_work import SqlPlayerImageUnitOfWork


def build_assign_player_image(session_factory: Callable[[], Session] | None = None) -> AssignPlayerImage:
    return AssignPlayerImage(SqlPlayerImageUnitOfWork(session_factory or (lambda: Session(engine))))


def build_get_player_images(
    session_factory: Callable[[], Session] | None = None,
) -> GetPlayerImages:
    return GetPlayerImages(SqlPlayerImageReader(session_factory or (lambda: Session(engine))))
