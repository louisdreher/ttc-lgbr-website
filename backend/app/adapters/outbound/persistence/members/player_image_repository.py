from sqlmodel import Session, select

from app.adapters.outbound.persistence.members.models import Player, PlayerImage as ImageRow
from app.core.members.domain.player_image import PlayerImage


class SqlPlayerImageRepository:
    def __init__(self, session: Session):
        self.session = session

    def lock_player(self, player_id: int) -> bool:
        # Serializes image changes across different teams containing the same player.
        return self.session.exec(select(Player.id).where(
            Player.id == player_id,
        ).with_for_update()).first() is not None

    def save(self, image: PlayerImage) -> None:
        row = self.session.get(ImageRow, (image.player_id, image.season_start_year, image.season_half))
        if row is None:
            row = ImageRow(player_id=image.player_id, season_start_year=image.season_start_year,
                           season_half=image.season_half, media_id=image.media_id)
        else:
            row.media_id = image.media_id
        self.session.add(row)
        self.session.flush()
