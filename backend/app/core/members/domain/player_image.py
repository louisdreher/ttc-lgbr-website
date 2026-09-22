from dataclasses import dataclass


@dataclass(frozen=True)
class PlayerImage:
    player_id: int
    season_start_year: int
    season_half: str
    media_id: int

    def __post_init__(self):
        if self.season_half not in ("vr", "rr"):
            raise ValueError("Unbekannte Halbserie.")
        if not 1 <= self.season_start_year <= 9998:
            raise ValueError("Ungültiges Saisonstartjahr.")
        if self.player_id < 1 or self.media_id < 1:
            raise ValueError("Spieler- und Medien-ID müssen positiv sein.")
