"""Input and output DTOs for the competition source and reader ports."""

from dataclasses import dataclass, field
from datetime import datetime

from app.core.competition.domain.seasons import SeasonKey


@dataclass(frozen=True, kw_only=True)
class GroupReference:
    id: int
    season: SeasonKey
    external_id: int
    external_slug: str | None
    team_external_id: int | None = None
    team_name: str | None = None


@dataclass(frozen=True, kw_only=True)
class ScheduledMatch:
    external_id: int
    group_external_id: int
    group_name: str
    group_slug: str
    team_external_id: int
    team_name: str
    opponent_name: str
    is_home: bool
    scheduled_at: datetime
    original_scheduled_at: datetime | None
    ended_at: datetime | None
    is_completed: bool
    status: str | None
    venue_name: str | None
    venue_street: str | None
    venue_city: str | None
    score_ttc: int | None
    score_opponent: int | None
    notices: dict[str, str | None] = field(default_factory=dict)


@dataclass(frozen=True)
class ScheduleSnapshot:
    matches: tuple[ScheduledMatch, ...]
    received_count: int


@dataclass(frozen=True, kw_only=True)
class ImportedPlayer:
    registration_id: str | None
    external_id: str | None
    first_name: str
    last_name: str
    rank: int | None = None
    absent: bool = False


@dataclass(frozen=True, kw_only=True)
class ImportedGame:
    kind: str
    external_id: str | None
    name: str | None
    home_players: tuple[ImportedPlayer, ...]
    away_players: tuple[ImportedPlayer, ...]
    sets: tuple[tuple[int, int, int], ...]
    played: bool

    def own_players(self, is_home: bool) -> tuple[ImportedPlayer, ...]:
        return self.home_players if is_home else self.away_players

    def opponent_name(self, is_home: bool) -> str | None:
        players = self.away_players if is_home else self.home_players
        names = [
            "Nicht anwesend" if p.absent else f"{p.first_name} {p.last_name}".strip()
            for p in players
        ]
        return " / ".join(name for name in names if name) or None


@dataclass(frozen=True, kw_only=True)
class MeetingDetails:
    completed: bool
    games: tuple[ImportedGame, ...] = ()
    started_at: datetime | None = None
    ended_at: datetime | None = None
    play_mode: str | None = None
    venue_name: str | None = None
    venue_street: str | None = None
    venue_city: str | None = None
    score_home: int | None = None
    score_away: int | None = None


@dataclass(frozen=True, kw_only=True)
class MeetingReference:
    id: int
    external_id: int
    imported: bool


@dataclass(frozen=True, kw_only=True)
class RegisteredPlayer:
    player: ImportedPlayer
    rank: str | None
    status: str | None


@dataclass(frozen=True, kw_only=True)
class Registration:
    team_name: str
    team_number: int | None
    players: tuple[RegisteredPlayer, ...]


@dataclass(frozen=True, kw_only=True)
class Standing:
    external_team_id: int
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
