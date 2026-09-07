from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class LeagueGroup(SQLModel, table=True):
    __tablename__ = "league_group"

    __table_args__ = (
        UniqueConstraint(
            "season_id",
            "mytt_group_id",
            name="uq_league_group_season_mytt",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)

    season_id: int = Field(
        foreign_key="season.id",
    )

    name: str

    mytt_group_id: int
    mytt_slug: str | None = None


class LeagueTableEntry(SQLModel, table=True):
    __tablename__ = "league_table_entry"

    __table_args__ = (
        UniqueConstraint(
            "league_group_id",
            "mytt_team_id",
            name="uq_league_table_entry_group_team",
        ),
    )

    id: int | None = Field(
        default=None,
        primary_key=True,
    )

    league_group_id: int = Field(
        foreign_key="league_group.id",
        index=True,
    )

    mytt_team_id: int
    club_id: str

    team_name: str
    position: int

    meetings_count: int

    meetings_won: int
    meetings_tie: int
    meetings_lost: int

    points_won: int
    points_lost: int

    matches_won: int
    matches_lost: int

    sets_won: int
    sets_lost: int

    games_won: int
    games_lost: int
