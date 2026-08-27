from enum import StrEnum

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class SeasonHalf(StrEnum):
    VR = "vr"
    RR = "rr"


class Season(SQLModel, table=True):
    __tablename__ = "season"

    __table_args__ = (
        UniqueConstraint(
            "start_year",
            "end_year",
            "half",
            name="uq_season_years_half",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)

    start_year: int
    end_year: int
    half: SeasonHalf
