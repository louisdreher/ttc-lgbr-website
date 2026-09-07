from datetime import datetime
from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class GameType(StrEnum):
    SINGLE = "single"
    DOUBLE = "double"


class TeamMatchNoticeCode(StrEnum):
    H = "H"
    T = "T"
    U = "U"
    V = "V"
    W = "W"
    W2 = "W2"
    Z = "Z"
    NA = "NA"


class TeamMatch(SQLModel, table=True):
    __tablename__ = "team_match"

    id: int | None = Field(default=None, primary_key=True)

    team_id: int = Field(
        foreign_key="team.id",
    )

    mytt_meeting_id: int | None = Field(
        default=None,
        unique=True,
        index=True,
    )

    opponent_name: str

    is_home: bool

    play_mode: str | None

    scheduled_at: datetime = Field(
        sa_type=sa.DateTime(timezone=True),
    )

    original_scheduled_at: datetime | None = Field(
        default=None,
        sa_type=sa.DateTime(timezone=True),
    )

    is_completed: bool = Field(
        default=False,
        index=True,
    )

    status: str

    started_at: datetime | None = Field(
        default=None,
        sa_type=sa.DateTime(timezone=True),
    )

    ended_at: datetime | None = Field(
        default=None,
        sa_type=sa.DateTime(timezone=True),
    )

    venue_name: str | None = None
    venue_street: str | None = None
    venue_city: str | None = None

    score_ttc: int | None = None
    score_opponent: int | None = None

    details_imported_at: datetime | None = Field(
        default=None,
        sa_type=sa.DateTime(timezone=True),
    )


class MatchLineup(SQLModel, table=True):
    __tablename__ = "match_lineup"

    team_match_id: int = Field(
        foreign_key="team_match.id",
        primary_key=True,
    )

    player_id: int = Field(
        foreign_key="player.id",
        primary_key=True,
    )

    position: int | None = None
    doubles_pair: int | None = None


class Match(SQLModel, table=True):
    __tablename__ = "match"

    __table_args__ = (
        UniqueConstraint(
            "team_match_id",
            "sequence",
            name="uq_match_team_match_sequence",
        ),
    )

    id: int | None = Field(
        default=None,
        primary_key=True,
    )

    team_match_id: int = Field(
        foreign_key="team_match.id",
    )

    sequence: int
    game_type: GameType
    match_name: str | None = None

    mytt_match_uuid: str | None = Field(
        default=None,
        unique=True,
        index=True,
    )


class MatchParticipant(SQLModel, table=True):
    __tablename__ = "match_participant"

    match_id: int = Field(
        foreign_key="match.id",
        primary_key=True,
    )

    player_id: int = Field(
        foreign_key="player.id",
        primary_key=True,
    )

    opponent_name: str | None = None


class SetResult(SQLModel, table=True):
    __tablename__ = "set_result"

    match_id: int = Field(
        foreign_key="match.id",
        primary_key=True,
    )

    set_number: int = Field(
        primary_key=True,
    )

    points_ttc: int
    points_opponent: int


class TeamMatchNotice(SQLModel, table=True):
    __tablename__ = "team_match_notice"

    team_match_id: int = Field(
        foreign_key="team_match.id",
        primary_key=True,
    )

    code: TeamMatchNoticeCode = Field(
        primary_key=True,
        sa_type=sa.String(2),
    )

    info: str | None = None
