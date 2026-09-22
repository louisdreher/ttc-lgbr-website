from collections.abc import Callable

from sqlalchemy import and_, case, func, or_
from sqlmodel import Session, select

from app.adapters.outbound.persistence.members.models import PlayerImage
from app.core.members.application.dto import GetPlayerImagesQuery


class SqlPlayerImageReader:
    def __init__(self, session_factory: Callable[[], Session]):
        self.session_factory = session_factory

    def read_images(self, query: GetPlayerImagesQuery) -> dict[int, int | None]:
        result = dict.fromkeys(query.player_ids)
        if not result:
            return result
        half_order = case((PlayerImage.season_half == "vr", 0), else_=1)
        requested_half = 0 if query.season_half == "vr" else 1
        candidates = (
            select(
                PlayerImage.player_id,
                PlayerImage.media_id,
                func.row_number().over(
                    partition_by=PlayerImage.player_id,
                    order_by=(PlayerImage.season_start_year.desc(), half_order.desc()),
                ).label("image_number"),
            )
            .where(
                PlayerImage.player_id.in_(query.player_ids),
                or_(
                    PlayerImage.season_start_year < query.season_start_year,
                    and_(
                        PlayerImage.season_start_year == query.season_start_year,
                        half_order <= requested_half,
                    ),
                ),
            )
            .subquery()
        )
        with self.session_factory() as session:
            rows = session.exec(
                select(candidates.c.player_id, candidates.c.media_id)
                .where(candidates.c.image_number == 1)
            ).all()
        result.update({player_id: media_id for player_id, media_id in rows})
        return result
