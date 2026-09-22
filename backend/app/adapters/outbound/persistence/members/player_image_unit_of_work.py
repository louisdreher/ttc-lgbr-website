from collections.abc import Callable

from sqlmodel import Session

from app.adapters.outbound.persistence.competition.public import assigned_player_period
from app.adapters.outbound.persistence.media.public import lock_image_reference
from app.adapters.outbound.persistence.members.player_image_repository import SqlPlayerImageRepository
from app.core.members.application.dto import PlayerImagePeriod


class SqlPlayerImageUnitOfWork:
    def __init__(self, session_factory: Callable[[], Session]):
        self.session_factory = session_factory

    def __enter__(self):
        self.session = self.session_factory()
        self.images = SqlPlayerImageRepository(self.session)
        return self

    def assignment_period(self, team_id: int, player_id: int) -> PlayerImagePeriod | None:
        period = assigned_player_period(self.session, team_id, player_id)
        return PlayerImagePeriod(*period) if period is not None else None

    def image_available(self, media_id: int) -> bool:
        return lock_image_reference(self.session, media_id)

    def commit(self):
        self.session.commit()

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.session.rollback()
        finally:
            self.session.close()
