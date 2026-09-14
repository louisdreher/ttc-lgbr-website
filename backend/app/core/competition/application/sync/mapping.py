"""Translate source data into domain entities for synchronization use cases."""

from dataclasses import dataclass
from datetime import datetime

from app.core.competition.application.sync.imports import (
    ImportedPlayer,
    MeetingDetails,
    Registration,
    ScheduledMatch,
)
from app.core.competition.domain.matches import (
    GameType,
    Match,
    MatchLineup,
    MatchParticipant,
    SetResult,
    TeamMatch,
    TeamMatchNotice,
    TeamMatchNoticeCode,
)


def apply_schedule(entity: TeamMatch, team_id: int, data: ScheduledMatch) -> None:
    entity.reschedule(
        data.scheduled_at, original_scheduled_at=data.original_scheduled_at
    )
    entity.team_id = team_id
    entity.opponent_name, entity.is_home = data.opponent_name, data.is_home
    entity.ended_at, entity.is_completed = data.ended_at, data.is_completed
    entity.venue_name, entity.venue_street, entity.venue_city = (
        data.venue_name,
        data.venue_street,
        data.venue_city,
    )
    entity.score_ttc, entity.score_opponent = data.score_ttc, data.score_opponent
    if data.status is not None:
        entity.status = data.status
    entity.notices = [
        TeamMatchNotice(
            team_match_id=entity.id, code=TeamMatchNoticeCode(code), info=info
        )
        for code, info in data.notices.items()
    ]
    # Schedule metadata does not replace imported details or the import marker.


def apply_meeting(
    entity: TeamMatch,
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
        for player in game.own_players(entity.is_home):
            if player.absent:
                continue
            player_id = player_ids[player]
            entry = lineup.setdefault(
                player_id, MatchLineup(team_match_id=entity.id, player_id=player_id)
            )
            if player.rank is not None:
                if game.kind == GameType.SINGLE:
                    entry.position = player.rank
                else:
                    entry.doubles_pair = player.rank
        if not game.played:
            continue
        match = Match(
            team_match_id=entity.id,
            sequence=sequence,
            game_type=GameType(game.kind),
            mytt_match_uuid=game.external_id,
            match_name=game.name,
        )
        participants = dict.fromkeys(
            player_ids[p] for p in game.own_players(entity.is_home)
        )
        match.participants = [
            MatchParticipant(
                player_id=player_id, opponent_name=game.opponent_name(entity.is_home)
            )
            for player_id in participants
        ]
        match.sets = [
            SetResult(
                set_number=number,
                points_ttc=home if entity.is_home else away,
                points_opponent=away if entity.is_home else home,
            )
            for number, home, away in game.sets
        ]
        matches.append(match)
    entity.record_result(
        completed=details.completed,
        matches=matches,
        lineup=list(lineup.values()),
        started_at=details.started_at,
        ended_at=details.ended_at,
        play_mode=details.play_mode,
        venue_name=details.venue_name,
        venue_street=details.venue_street,
        venue_city=details.venue_city,
        score_ttc=details.score_home if entity.is_home else details.score_away,
        score_opponent=details.score_away if entity.is_home else details.score_home,
    )
    entity.details_imported_at = imported_at


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
