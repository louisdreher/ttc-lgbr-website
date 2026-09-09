from __future__ import annotations

from dataclasses import dataclass

from app.core.competition.domain.imports import SeasonHalf, SeasonKey


@dataclass(kw_only=True)
class Season:
    id: int | None = None
    start_year: int
    end_year: int
    half: SeasonHalf

    def __post_init__(self):
        SeasonKey(self.start_year, self.end_year, self.half)

    @property
    def key(self) -> SeasonKey:
        return SeasonKey(self.start_year, self.end_year, self.half)
