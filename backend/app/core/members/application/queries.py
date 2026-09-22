from app.core.members.application.dto import GetPlayerImagesQuery
from app.core.members.application.ports import PlayerImageReader


class GetPlayerImages:
    def __init__(self, reader: PlayerImageReader):
        self.reader = reader

    def execute(self, query: GetPlayerImagesQuery) -> dict[int, int | None]:
        if not query.player_ids:
            return {}
        return self.reader.read_images(query)
