from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.core.competition.domain.imports import (
    ImportedPlayer,
    MeetingDetails,
    ScheduledMatch,
    original_schedule,
)
from app.core.competition.domain.types import GameType, TeamMatchNoticeCode


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

    @classmethod
    def from_schedule(cls, team_id: int, data: ScheduledMatch) -> TeamMatch:
        match = cls(
            team_id=team_id,
            mytt_meeting_id=data.external_id,
            opponent_name=data.opponent_name,
            is_home=data.is_home,
            scheduled_at=data.scheduled_at,
            status=data.status or "unknown",
        )
        match.update_schedule(team_id, data)
        return match

    def update_schedule(self, team_id: int, data: ScheduledMatch) -> None:
        self.reschedule(
            data.scheduled_at, original_scheduled_at=data.original_scheduled_at
        )
        self.team_id = team_id
        self.opponent_name, self.is_home = data.opponent_name, data.is_home
        self.ended_at, self.is_completed = data.ended_at, data.is_completed
        self.venue_name, self.venue_street, self.venue_city = (
            data.venue_name,
            data.venue_street,
            data.venue_city,
        )
        self.score_ttc, self.score_opponent = data.score_ttc, data.score_opponent
        if data.status is not None:
            self.status = data.status
        self.notices = [
            TeamMatchNotice(
                team_match_id=self.id, code=TeamMatchNoticeCode(code), info=info
            )
            for code, info in data.notices.items()
        ]
        # Schedule metadata does not replace imported details or the import marker.

    def import_details(
        self,
        details: MeetingDetails,
        player_ids: dict[ImportedPlayer, int],
        imported_at: datetime,
    ) -> None:
        if not details.completed:
            raise ValueError(
                "Nur abgeschlossene Begegnungen können Detaildaten übernehmen."
            )
        lineup = {}
        matches = []
        for sequence, game in enumerate(details.games, 1):
            for player in game.own_players(self.is_home):
                if player.absent:
                    continue
                player_id = player_ids[player]
                entry = lineup.setdefault(
                    player_id, MatchLineup(team_match_id=self.id, player_id=player_id)
                )
                if player.rank is not None:
                    if game.kind == GameType.SINGLE:
                        entry.position = player.rank
                    else:
                        entry.doubles_pair = player.rank
            if not game.played:
                continue
            match = Match(
                team_match_id=self.id,
                sequence=sequence,
                game_type=GameType(game.kind),
                mytt_match_uuid=game.external_id,
                match_name=game.name,
            )
            participants = dict.fromkeys(
                player_ids[p] for p in game.own_players(self.is_home)
            )
            match.participants = [
                MatchParticipant(
                    player_id=player_id, opponent_name=game.opponent_name(self.is_home)
                )
                for player_id in participants
            ]
            match.sets = [
                SetResult(
                    set_number=number,
                    points_ttc=home if self.is_home else away,
                    points_opponent=away if self.is_home else home,
                )
                for number, home, away in game.sets
            ]
            matches.append(match)
        # Build the replacement completely before mutating the aggregate.
        self.matches, self.lineup = matches, list(lineup.values())
        self.is_completed = True
        for name in (
            "started_at",
            "ended_at",
            "play_mode",
            "venue_name",
            "venue_street",
            "venue_city",
        ):
            value = getattr(details, name)
            if value:
                setattr(self, name, value)
        if details.score_home is not None and details.score_away is not None:
            self.score_ttc, self.score_opponent = (
                (details.score_home, details.score_away)
                if self.is_home
                else (details.score_away, details.score_home)
            )
        self.details_imported_at = imported_at


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
