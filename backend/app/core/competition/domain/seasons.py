from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class SeasonHalf(StrEnum):
    VR = "vr"
    RR = "rr"


@dataclass(frozen=True)
class SeasonKey:
    start_year: int
    end_year: int
    half: SeasonHalf

    def __post_init__(self):
        if self.end_year != self.start_year + 1:
            raise ValueError("end_year muss start_year + 1 sein.")
        if self.half not in (SeasonHalf.VR, SeasonHalf.RR):
            raise ValueError("Unbekannte Halbserie")

    @property
    def period(self) -> tuple[date, date]:
        if self.half == SeasonHalf.VR:
            return date(self.start_year, 7, 1), date(self.start_year, 12, 31)
        return date(self.end_year, 1, 1), date(self.end_year, 6, 30)

    @classmethod
    def current(cls, today: date) -> SeasonKey:
        if today.month <= 6:
            return cls(today.year - 1, today.year, SeasonHalf.RR)
        return cls(today.year, today.year + 1, SeasonHalf.VR)


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
