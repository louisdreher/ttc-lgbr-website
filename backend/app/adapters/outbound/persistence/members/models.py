from datetime import date

from sqlalchemy import CheckConstraint
from sqlmodel import Field, SQLModel


class Member(SQLModel, table=True):
    __tablename__ = "member"

    id: int | None = Field(default=None, primary_key=True)

    last_name: str
    first_name: str

    birth_date: date | None = None

    joined_at: date | None = None

    # Spielberechtigung
    eligible_since: date | None = None
    ttc_eligible_since: date | None = None

    # Aktive/passive Vereinsmitgliedschaft
    is_active: bool = True

    # Vereinsaustritt
    membership_end_date: date | None = None

    phone: str | None = None
    mobile: str | None = None
    email: str | None = None

    street: str | None = None
    house_number: str | None = None
    postal_code: str | None = None
    city: str | None = None


class Player(SQLModel, table=True):
    __tablename__ = "player"

    id: int | None = Field(default=None, primary_key=True)

    member_id: int = Field(
        foreign_key="member.id",
        unique=True,
    )

    mytt_person_id: str | None = Field(
        default=None,
        unique=True,
        index=True,
    )

    nuid: str | None = Field(
        default=None,
        unique=True,
        index=True,
    )


class PlayerRating(SQLModel, table=True):
    __tablename__ = "player_rating"

    player_id: int = Field(
        foreign_key="player.id",
        primary_key=True,
    )

    effective_date: date = Field(
        primary_key=True,
    )

    qttr: int


class PlayerImage(SQLModel, table=True):
    """One image per player and season half."""

    __tablename__ = "player_image"
    __table_args__ = (
        CheckConstraint("season_half IN ('vr', 'rr')", name="ck_player_image_season_half"),
    )

    player_id: int = Field(foreign_key="player.id", primary_key=True)
    # 2026 represents 2026/27. Intentionally independent of half-season IDs.
    season_start_year: int = Field(primary_key=True)
    season_half: str = Field(primary_key=True)
    media_id: int = Field(foreign_key="media_asset.id")
