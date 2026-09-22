from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class AssignPlayerImageCommand:
    team_id: int
    player_id: int
    media_id: int
    can_manage: bool = False


@dataclass(frozen=True)
class PlayerImagePeriod:
    start_year: int
    half: str


@dataclass(frozen=True)
class GetPlayerImagesQuery:
    player_ids: frozenset[int]
    season_start_year: int
    season_half: Literal["vr", "rr"]

    def __post_init__(self):
        if self.season_half not in ("vr", "rr"):
            raise ValueError("Unbekannte Halbserie.")
        if type(self.season_start_year) is not int or not 1 <= self.season_start_year <= 9998:
            raise ValueError("Ungültiges Saisonstartjahr.")
        if any(type(player_id) is not int or player_id <= 0 for player_id in self.player_ids):
            raise ValueError("Spieler-IDs müssen positiv sein.")
