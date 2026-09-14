from collections.abc import Callable

from sqlmodel import Session, select

from app.adapters.outbound.persistence.members.models import Member, Player
from app.core.competition.application.dto import MatchPlayer


class SqlMatchPlayerReader:
    def __init__(self, session_factory: Callable[[], Session]):
        self.session_factory = session_factory

    def read_players(self, player_ids: set[int]) -> dict[int, MatchPlayer]:
        if not player_ids:
            return {}
        with self.session_factory() as session:
            rows = session.exec(
                select(Player.id, Member.first_name, Member.last_name)
                .join(Member, Player.member_id == Member.id)
                .where(Player.id.in_(player_ids))
            ).all()
            return {
                row.id: MatchPlayer(row.id, row.first_name, row.last_name)
                for row in rows
            }
