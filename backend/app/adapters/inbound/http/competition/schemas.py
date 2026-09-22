from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TeamSummaryRead(ReadModel):
    id: int
    name: str
    team_number: int | None
    category: str | None


class ScheduledMatchSummaryRead(ReadModel):
    id: int
    team_id: int
    team_name: str
    opponent_name: str
    is_home: bool
    scheduled_at: datetime
    status: str
    is_completed: bool
    score_ttc: int | None
    score_opponent: int | None


class StandingSummaryRead(ReadModel):
    team_name: str
    position: int
    is_selected_team: bool
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


class MatchPlayerRead(ReadModel):
    player_id: int
    first_name: str
    last_name: str


class MatchLineupEntryRead(ReadModel):
    player: MatchPlayerRead
    position: int | None
    doubles_pair: int | None


class MatchSetRead(ReadModel):
    set_number: int
    points_ttc: int
    points_opponent: int


class MatchGameRead(ReadModel):
    id: int
    sequence: int
    game_type: str
    name: str | None
    players: list[MatchPlayerRead]
    opponent_names: list[str]
    sets: list[MatchSetRead]


class MatchNoticeRead(ReadModel):
    code: str
    info: str | None


class MatchDetailsRead(ReadModel):
    id: int
    team_id: int
    team_name: str
    opponent_name: str
    is_home: bool
    scheduled_at: datetime
    original_scheduled_at: datetime | None
    started_at: datetime | None
    ended_at: datetime | None
    status: str
    is_completed: bool
    score_ttc: int | None
    score_opponent: int | None
    play_mode: str | None
    venue_name: str | None
    venue_street: str | None
    venue_city: str | None
    details_available: bool
    notices: list[MatchNoticeRead] = Field(default_factory=list)
    lineup: list[MatchLineupEntryRead] = Field(default_factory=list)
    games: list[MatchGameRead] = Field(default_factory=list)


class TeamLineupEntryRead(ReadModel):
    player_id: int
    first_name: str
    last_name: str
    position: int | None
    status: str | None
    media_id: int | None = None


class TeamLineupRead(ReadModel):
    team_id: int
    team_name: str
    season_id: int
    category: str | None
    players: list[TeamLineupEntryRead] = Field(default_factory=list)


class SeasonSummaryRead(ReadModel):
    id: int
    start_year: int
    end_year: int
    half: Literal["vr", "rr"]


class PlayerCandidateRead(ReadModel):
    player_id: int
    first_name: str
    last_name: str
    team_number: int | None
    rank: str | None


class PlayerImageWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    media_id: int = Field(gt=0, strict=True)
