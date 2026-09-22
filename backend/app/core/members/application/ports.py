from typing import Protocol, Self

from app.core.members.application.dto import GetPlayerImagesQuery
from app.core.members.application.dto import PlayerImagePeriod
from app.core.members.domain.player_image import PlayerImage


class PlayerImageRepository(Protocol):
    def lock_player(self, player_id: int) -> bool: ...
    def save(self, image: PlayerImage) -> None:
        """Replace only the exact player/year/half entry, without committing."""
        ...


class PlayerImageUnitOfWork(Protocol):
    images: PlayerImageRepository

    def assignment_period(self, team_id: int, player_id: int) -> PlayerImagePeriod | None:
        """Lock the team and verify its internal player assignment in this transaction."""
        ...
    def image_available(self, media_id: int) -> bool:
        """Validate and hold a processed image reference until commit."""
        ...
    def __enter__(self) -> Self: ...
    def __exit__(self, exc_type, exc_value, traceback) -> None: ...
    def commit(self) -> None: ...


class PlayerImageReader(Protocol):
    def read_images(self, query: GetPlayerImagesQuery) -> dict[int, int | None]:
        """Return an image ID or None for every requested player, including unknown IDs."""
        ...
