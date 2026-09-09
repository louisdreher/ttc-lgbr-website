"""Provider-independent snapshots and rules for competition imports."""

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
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
    def current(cls, today: date) -> "SeasonKey":
        if today.month <= 6:
            return cls(today.year - 1, today.year, SeasonHalf.RR)
        return cls(today.year, today.year + 1, SeasonHalf.VR)


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


def original_schedule(
    previous: datetime,
    current: datetime,
    known_original: datetime | None,
    supplied_original: datetime | None,
) -> datetime | None:
    if supplied_original is not None:
        return supplied_original

    # Offset-free imported dates are compared as UTC, as in the existing import.
    def comparable(value):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

    if known_original is None and comparable(previous) != comparable(current):
        return previous
    return known_original


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


@dataclass(frozen=True)
class RegistrationTeam:
    id: int
    name: str
    number: int | None


def find_registration_team(
    teams: list[RegistrationTeam], registration: Registration
) -> int | None:
    if len(teams) == 1:
        return teams[0].id
    if registration.team_number is not None:
        matches = [team for team in teams if team.number == registration.team_number]
        if len(matches) == 1:
            return matches[0].id

    def normalized(name):
        return " ".join(name.split()).casefold()

    matches = [
        team
        for team in teams
        if normalized(team.name) == normalized(registration.team_name)
    ]
    return matches[0].id if len(matches) == 1 else None
