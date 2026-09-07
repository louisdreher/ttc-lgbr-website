from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class Team(SQLModel, table=True):
    __tablename__ = "team"

    __table_args__ = (
        UniqueConstraint(
            "season_id",
            "mytt_team_id",
            name="uq_team_season_mytt",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)

    season_id: int = Field(
        foreign_key="season.id",
    )

    league_group_id: int = Field(
        foreign_key="league_group.id",
    )

    mytt_team_id: int

    name: str
    team_number: int | None = None
    category: str | None = None


class TeamMembership(SQLModel, table=True):
    __tablename__ = "team_membership"

    team_id: int = Field(
        foreign_key="team.id",
        primary_key=True,
    )

    player_id: int = Field(
        foreign_key="player.id",
        primary_key=True,
    )

    # z. B. "1.3", "2.2", "3.1"
    rank: str | None = None

    status: str | None = None


class TeamAssignment(SQLModel, table=True):
    __tablename__ = "team_assignment"

    team_id: int = Field(
        foreign_key="team.id",
        primary_key=True,
    )

    player_id: int = Field(
        foreign_key="player.id",
        primary_key=True,
    )

    position: int | None = None
    status: str | None = None
