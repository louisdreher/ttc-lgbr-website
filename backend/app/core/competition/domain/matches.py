from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum


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


@dataclass(kw_only=True)
class TeamMatch:
    id: int | None = None
    team_id: int
    mytt_meeting_id: int | None = None
    opponent_name: str
    is_home: bool
    play_mode: str | None = None
    scheduled_at: datetime
    original_scheduled_at: datetime | None = None
    is_completed: bool = False
    status: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    venue_name: str | None = None
    venue_street: str | None = None
    venue_city: str | None = None
    score_ttc: int | None = None
    score_opponent: int | None = None
    details_imported_at: datetime | None = None
    notices: list[TeamMatchNotice] = field(default_factory=list)
    lineup: list[MatchLineup] = field(default_factory=list)
    matches: list[Match] = field(default_factory=list)

    def reschedule(
        self, scheduled_at: datetime, *, original_scheduled_at: datetime | None = None
    ) -> None:
        self.original_scheduled_at = original_schedule(
            self.scheduled_at,
            scheduled_at,
            self.original_scheduled_at,
            original_scheduled_at,
        )
        self.scheduled_at = scheduled_at

    def record_result(
        self,
        *,
        completed: bool,
        matches: list[Match],
        lineup: list[MatchLineup],
        started_at: datetime | None = None,
        ended_at: datetime | None = None,
        play_mode: str | None = None,
        venue_name: str | None = None,
        venue_street: str | None = None,
        venue_city: str | None = None,
        score_ttc: int | None = None,
        score_opponent: int | None = None,
    ) -> None:
        if not completed:
            raise ValueError(
                "Nur abgeschlossene Begegnungen können Detaildaten übernehmen."
            )
        self.matches, self.lineup = matches, lineup
        self.is_completed = True
        for name, value in (
            ("started_at", started_at),
            ("ended_at", ended_at),
            ("play_mode", play_mode),
            ("venue_name", venue_name),
            ("venue_street", venue_street),
            ("venue_city", venue_city),
        ):
            if value:
                setattr(self, name, value)
        if score_ttc is not None and score_opponent is not None:
            self.score_ttc, self.score_opponent = score_ttc, score_opponent


@dataclass(kw_only=True)
class MatchLineup:
    team_match_id: int | None = None
    player_id: int
    position: int | None = None
    doubles_pair: int | None = None


@dataclass(kw_only=True)
class Match:
    id: int | None = None
    team_match_id: int | None = None
    sequence: int
    game_type: GameType
    match_name: str | None = None
    mytt_match_uuid: str | None = None
    participants: list[MatchParticipant] = field(default_factory=list)
    sets: list[SetResult] = field(default_factory=list)


@dataclass(kw_only=True)
class MatchParticipant:
    match_id: int | None = None
    player_id: int
    opponent_name: str | None = None


@dataclass(kw_only=True)
class SetResult:
    match_id: int | None = None
    set_number: int
    points_ttc: int
    points_opponent: int


@dataclass(kw_only=True)
class TeamMatchNotice:
    team_match_id: int | None = None
    code: TeamMatchNoticeCode
    info: str | None = None

    def __post_init__(self):
        self.code = TeamMatchNoticeCode(self.code)
