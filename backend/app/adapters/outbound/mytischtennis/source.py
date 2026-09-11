"""Validate myTischtennis responses and translate them into core snapshots."""

import json
import logging
from datetime import datetime

import httpx

from app.core.competition.application.imports import (
    GroupReference,
    ImportedGame,
    ImportedPlayer,
    MeetingDetails,
    RegisteredPlayer,
    Registration,
    ScheduledMatch,
    ScheduleSnapshot,
    Standing,
)
from app.core.competition.application.ports import SourceError
from app.core.competition.domain.seasons import SeasonKey

logger = logging.getLogger(__name__)
ABSENT_PLAYER_ID = "NU74837"
NOTICE_FIELDS = {
    "H": ("is_letter_h", "letter_h_info"),
    "T": ("is_letter_t", None),
    "U": ("is_letter_u", None),
    "V": ("is_letter_v", None),
    "W": ("is_letter_w", "letter_w_info"),
    "W2": ("is_letter_w2", None),
    "Z": ("is_letter_z", "letter_z_info"),
    "NA": ("is_letter_na", "letter_na_info"),
}


def integer(value):
    return int(value) if value is not None else None


def timestamp(value):
    return datetime.fromisoformat(str(value)) if value else None


def string(value):
    return str(value).strip() if value is not None else ""


def required(data, key):
    if key not in data or data[key] is None or not string(data[key]):
        raise ValueError(f"Pflichtfeld {key!r} fehlt.")
    return data[key]


def object_value(value):
    if not isinstance(value, dict):
        raise TypeError("Objekt erwartet.")
    return value


def list_value(value):
    if not isinstance(value, list):
        raise TypeError("Liste erwartet.")
    return value


def season_name(season):
    return f"{season.start_year % 100:02d}--{season.end_year % 100:02d}"


class MyTischtennisSource:
    def __init__(self, client, club_number: str):
        self.client = client
        self.club_number = str(club_number)

    async def _request(self, method, **kwargs):
        try:
            result = object_value(await method(**kwargs))
            if result.get("error"):
                raise SourceError("myTischtennis meldet einen API-Fehler.")
            return result
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            raise SourceError(
                f"myTischtennis HTTP {status}",
                retryable=status in {403, 408, 429} or status >= 500,
            ) from exc
        except httpx.RequestError as exc:
            raise SourceError(
                "myTischtennis ist nicht erreichbar.", retryable=True
            ) from exc
        except json.JSONDecodeError as exc:
            raise SourceError("Ungültige JSON-Antwort.", retryable=True) from exc
        except (ValueError, TypeError) as exc:
            raise SourceError("Ungültige Antwortstruktur.") from exc

    async def schedule(self, season: SeasonKey) -> ScheduleSnapshot:
        start, end = season.period
        response = await self._request(
            self.client.get_club_schedule_data,
            date_start=start,
            date_end=end,
            season=season_name(season),
        )
        try:
            data = response.get("data")
            if data is None:
                raise ValueError("Schedule: data fehlt.")
            if data == []:  # Observed empty response variant.
                return ScheduleSnapshot((), 0)
            meetings = [
                object_value(row)
                for day in object_value(data).values()
                for row in list_value(day)
            ]
            deduplicated = {int(required(row, "meeting_id")): row for row in meetings}
            # Cups and relegation remain unsupported, as in the previous importer.
            supported = [
                row
                for row in deduplicated.values()
                if string(row.get("round_type")) in {"0", "1"}
            ]
            logger.info(
                "Spielplan geladen: total=%s supported=%s",
                len(deduplicated),
                len(supported),
            )
            return ScheduleSnapshot(
                tuple(self._scheduled_match(row) for row in supported),
                len(deduplicated),
            )
        except (ValueError, TypeError, KeyError) as exc:
            raise SourceError(f"Ungültiger Spielplan: {exc}") from exc

    def _scheduled_match(self, row):
        home = string(required(row, "team_home_club_id")) == self.club_number
        if not home and string(required(row, "team_away_club_id")) != self.club_number:
            raise ValueError("Begegnung gehört nicht zum eigenen Verein.")
        own, other = ("home", "away") if home else ("away", "home")
        location = object_value(row.get("location") or {})
        completed = bool(row.get("is_meeting_complete", False))
        score_home = integer(row.get("matches_won")) if completed else None
        score_away = integer(row.get("matches_lost")) if completed else None
        league_name = str(required(row, "league_name"))
        return ScheduledMatch(
            external_id=int(required(row, "meeting_id")),
            group_external_id=int(required(row, "league_id")),
            group_name=league_name.strip(),
            group_slug=league_name.replace(" ", "_"),
            team_external_id=int(required(row, f"team_{own}_id")),
            team_name=string(required(row, f"team_{own}")),
            opponent_name=string(required(row, f"team_{other}")),
            is_home=home,
            scheduled_at=timestamp(required(row, "date")),
            original_scheduled_at=timestamp(row.get("original_date")),
            ended_at=timestamp(row.get("end_date")),
            is_completed=completed,
            status=row.get("state"),
            venue_name=location.get("label"),
            venue_street=location.get("street"),
            venue_city=location.get("city"),
            score_ttc=score_home if home else score_away,
            score_opponent=score_away if home else score_home,
            notices={
                code: row.get(info) if info else None
                for code, (flag, info) in NOTICE_FIELDS.items()
                if row.get(flag)
            },
        )

    async def meeting(self, external_id: int) -> MeetingDetails:
        response = await self._request(self.client.get_meeting, meeting_id=external_id)
        try:
            data = object_value(response.get("data"))
            completed = (
                data.get("is_completed") is True
                or data.get("is_meeting_complete") is True
            )
            if not completed:
                return MeetingDetails(completed=False)
            location = data.get("location")
            location = location if isinstance(location, dict) else {}
            return MeetingDetails(
                completed=True,
                games=tuple(
                    self._game(object_value(row))
                    for row in list_value(data.get("match"))
                ),
                started_at=timestamp(data.get("start_date")),
                ended_at=timestamp(data.get("end_date")),
                play_mode=string(data.get("play_mode")) or None,
                venue_name=location.get("label")
                or (
                    data.get("court_hall_name")
                    if isinstance(data.get("location"), dict)
                    else None
                ),
                venue_street=location.get("street"),
                venue_city=location.get("city"),
                score_home=integer(data.get("matches_home")),
                score_away=integer(data.get("matches_guest")),
            )
        except (ValueError, TypeError, KeyError) as exc:
            raise SourceError(f"Ungültige Begegnungsdetails: {exc}") from exc

    def _player(self, row):
        return ImportedPlayer(
            registration_id=string(row.get("person_id")) or None,
            external_id=string(row.get("player_id")) or None,
            first_name=string(row.get("firstname")),
            last_name=string(row.get("lastname")),
            rank=integer(row.get("player_rank")),
            absent=string(row.get("person_id")) == ABSENT_PLAYER_ID,
        )

    def _game(self, row):
        kind = required(row, "game_type")
        if kind not in {"single", "double"}:
            raise ValueError("Unbekannter game_type.")
        sets = []
        for number in range(1, 6):
            home, away = (
                integer(row.get(f"set{number}_home")),
                integer(row.get(f"set{number}_guest")),
            )
            if home is not None and away is not None and (home != 0 or away != 0):
                sets.append((number, home, away))
        return ImportedGame(
            kind=kind,
            external_id=string(row.get("match_uuid")) or None,
            name=string(row.get("match_name")) or None,
            home_players=tuple(
                self._player(row[key])
                for key in ("mm_player11", "mm_player12")
                if isinstance(row.get(key), dict)
            ),
            away_players=tuple(
                self._player(row[key])
                for key in ("mm_player21", "mm_player22")
                if isinstance(row.get(key), dict)
            ),
            sets=tuple(sets),
            played=(integer(row.get("matches_home")) or 0) > 0
            or (integer(row.get("matches_guest")) or 0) > 0
            or any(
                bool(row.get(key))
                for key in ("home_wo", "guest_wo", "home_penalty", "guest_penalty")
            ),
        )

    async def registrations(self, group: GroupReference) -> tuple[Registration, ...]:
        response = await self._request(
            self.client.get_team_registrations,
            season=season_name(group.season),
            league_slug=group.external_slug,
            group_id=group.external_id,
            round_filter=group.season.half.value,
        )
        try:
            pools = list_value(object_value(response.get("data")).get("teampools", []))
            registrations = []
            for pool in pools:
                pool = object_value(pool)
                if string(pool.get("clubnr")) != self.club_number:
                    continue
                players = list_value(pool.get("teampool"))
                numbers = {
                    int(p["team_number"])
                    for p in players
                    if object_value(p).get("team_number") is not None
                }
                if len(numbers) > 1:
                    raise ValueError("Mehrere Mannschaftsnummern in einer Meldung.")
                registered = []
                for player in players:
                    # Reject an incomplete snapshot before replacing memberships.
                    nuid = string(required(player, "player_id"))
                    registered.append(
                        RegisteredPlayer(
                            player=ImportedPlayer(
                                registration_id=nuid,
                                external_id=None,
                                first_name=string(player.get("player_firstname")),
                                last_name=string(player.get("player_lastname")),
                            ),
                            rank=str(player["player_rank"])
                            if player.get("player_rank") is not None
                            else None,
                            status=player.get("player_status"),
                        )
                    )
                registrations.append(
                    Registration(
                        team_name=string(pool.get("team_name")),
                        team_number=next(iter(numbers)) if numbers else None,
                        players=tuple(registered),
                    )
                )
            return tuple(registrations)
        except (ValueError, TypeError, KeyError) as exc:
            raise SourceError(f"Ungültige Mannschaftsmeldung: {exc}") from exc

    async def standings(self, group: GroupReference) -> tuple[Standing, ...]:
        response = await self._request(
            self.client.get_team_player_balances,
            season=season_name(group.season),
            league_slug=group.external_slug,
            group_id=group.external_id,
            team_id=group.team_external_id,
            team_name=group.team_name,
            round_filter=group.season.half.value,
        )
        try:
            actual_id = integer(response.get("urlid"))
            if actual_id is not None and actual_id != group.external_id:
                raise ValueError("Antwort gehört zu einer anderen Ligagruppe.")
            rows = list_value(object_value(response.get("tableData")).get("table"))
            return tuple(
                Standing(
                    external_team_id=int(required(object_value(row), "team_id")),
                    club_id=string(required(row, "club_id")),
                    team_name=string(required(row, "team_name")),
                    position=int(required(row, "table_rank")),
                    **{
                        key: int(required(row, key))
                        for key in (
                            "meetings_count",
                            "meetings_won",
                            "meetings_tie",
                            "meetings_lost",
                            "points_won",
                            "points_lost",
                            "matches_won",
                            "matches_lost",
                            "sets_won",
                            "sets_lost",
                            "games_won",
                            "games_lost",
                        )
                    },
                )
                for row in rows
            )
        except (ValueError, TypeError, KeyError) as exc:
            raise SourceError(f"Ungültige Ligatabelle: {exc}") from exc
