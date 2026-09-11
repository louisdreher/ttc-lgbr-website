from collections.abc import Callable

from sqlmodel import Session

from app.adapters.outbound.persistence.members.models import Player


class SqlPlayerLookup:
    def __init__(self, session_factory: Callable[[], Session]):
        self.session_factory = session_factory

    def exists(self, player_id: int) -> bool:
        with self.session_factory() as session:
            return session.get(Player, player_id) is not None
