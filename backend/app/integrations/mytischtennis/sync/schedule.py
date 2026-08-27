from datetime import date, datetime
from enum import StrEnum

from app.core.database import engine
from app.core.settings import settings
from app.domains.competition.league.model import LeagueGroup
from app.domains.competition.matches.models import (
    TeamMatch,
    TeamMatchNotice,
    TeamMatchNoticeCode,
)
from app.domains.competition.season.model import Season, SeasonHalf
from app.domains.competition.teams.model import Team
from app.integrations.mytischtennis.api import (
    MyTischtennisClient,
)
from sqlmodel import Session, select

# =============================================================================
# Wettbewerbsart
# =============================================================================


class ScheduleCompetition(StrEnum):
    LEAGUE = "league"
    RELEGATION = "relegation"
    CUP = "cup"
    UNKNOWN = "unknown"


# -----------------------------------------------------------------------------
# Zuordnung der myTT-round_type-Werte
#
# Aktuell haben wir in den Schedule-Daten beobachtet:
#
#   0 = normale Punktrunde
#   1 = normale Punktrunde, Rückrunde
#   4 = Pokal
#
# Falls myTT später weitere Wettbewerbsarten liefert, müssen diese nur hier
# ergänzt und anschließend im Dispatcher _sync_meeting() behandelt werden.
# -----------------------------------------------------------------------------

ROUND_TYPE_COMPETITION_MAP = {
    "0": ScheduleCompetition.LEAGUE,
    "1": ScheduleCompetition.LEAGUE,  # Rückrunde
    "3": ScheduleCompetition.RELEGATION,
    "4": ScheduleCompetition.CUP,
}


# =============================================================================
# Notices
# =============================================================================

NOTICE_FIELDS = {
    TeamMatchNoticeCode.H: ("is_letter_h", "letter_h_info"),
    TeamMatchNoticeCode.T: ("is_letter_t", None),
    TeamMatchNoticeCode.U: ("is_letter_u", None),
    TeamMatchNoticeCode.V: ("is_letter_v", None),
    TeamMatchNoticeCode.W: ("is_letter_w", "letter_w_info"),
    TeamMatchNoticeCode.W2: ("is_letter_w2", None),
    TeamMatchNoticeCode.Z: ("is_letter_z", "letter_z_info"),
    TeamMatchNoticeCode.NA: ("is_letter_na", "letter_na_info"),
}


# =============================================================================
# ScheduleSync
# =============================================================================


class ScheduleSync:
    def __init__(self):
        self.client = MyTischtennisClient()

    # =========================================================================
    # Öffentlicher Einstieg
    # =========================================================================

    async def sync(
        self,
        start_year: int,
        end_year: int,
        half: SeasonHalf,
    ) -> None:

        season_string = self._build_mytt_season_name(
            start_year=start_year,
            end_year=end_year,
        )

        date_start, date_end = self._get_period(
            start_year=start_year,
            end_year=end_year,
            half=half,
        )

        print()
        print("=" * 60)
        print("MYTT SCHEDULE SYNC")
        print("=" * 60)

        print(f"Saison: {start_year}/{str(end_year)[-2:]} {half.value.upper()}")

        print(f"Zeitraum: {date_start} - {date_end}")

        # =====================================================================
        # Schedule von myTT laden
        # =====================================================================

        result = await self.client.get_club_schedule_data(
            date_start=date_start,
            date_end=date_end,
            season=season_string,
        )

        api_error = result.get("error")

        if api_error:
            raise RuntimeError(f"myTischtennis meldet einen Fehler: {api_error}")

        data = result.get("data")

        if not data:
            print("Keine Begegnungen gefunden.")

            return

        # =====================================================================
        # Begegnungen aus Tagesgruppen herausziehen
        # =====================================================================

        meetings = [meeting for day in data.values() for meeting in day]

        # ---------------------------------------------------------------------
        # Sicherheitshalber anhand meeting_id deduplizieren
        # ---------------------------------------------------------------------

        meetings = list(
            {int(meeting["meeting_id"]): meeting for meeting in meetings}.values()
        )

        print(f"{len(meetings)} Begegnungen gefunden")

        # =====================================================================
        # DB synchronisieren
        # =====================================================================

        with Session(engine) as session:
            season = self._get_or_create_season(
                session=session,
                start_year=start_year,
                end_year=end_year,
                half=half,
            )

            # -----------------------------------------------------------------
            # Statistik
            # -----------------------------------------------------------------

            created_matches = 0
            updated_matches = 0
            skipped_matches = 0

            skipped_competitions: dict[
                ScheduleCompetition,
                int,
            ] = {
                ScheduleCompetition.CUP: 0,
                ScheduleCompetition.UNKNOWN: 0,
            }

            # -----------------------------------------------------------------
            # Meetings verarbeiten
            # -----------------------------------------------------------------

            for meeting in meetings:
                (
                    action,
                    competition,
                ) = self._sync_meeting(
                    session=session,
                    season=season,
                    meeting=meeting,
                )

                # -------------------------------------------------------------
                # Angelegt
                # -------------------------------------------------------------

                if action == "created":
                    created_matches += 1

                # -------------------------------------------------------------
                # Aktualisiert
                # -------------------------------------------------------------

                elif action == "updated":
                    updated_matches += 1

                # -------------------------------------------------------------
                # Fachlich übersprungen
                # -------------------------------------------------------------

                elif action == "skipped":
                    skipped_matches += 1

                # -------------------------------------------------------------
                # Wettbewerbsart wird momentan noch nicht importiert
                # -------------------------------------------------------------

                elif action == "unsupported":
                    skipped_competitions.setdefault(
                        competition,
                        0,
                    )

                    skipped_competitions[competition] += 1

                else:
                    raise RuntimeError(f"Unbekannte Sync-Aktion: {action}")

            session.commit()

        # =====================================================================
        # Zusammenfassung
        # =====================================================================

        print()
        print("Synchronisation abgeschlossen:")

        print(f"  Begegnungen neu:          {created_matches}")

        print(f"  Begegnungen aktualisiert: {updated_matches}")

        print(f"  Begegnungen übersprungen: {skipped_matches}")

        # ---------------------------------------------------------------------
        # Nicht unterstützte Wettbewerbe separat anzeigen
        # ---------------------------------------------------------------------

        cup_count = skipped_competitions.get(
            ScheduleCompetition.CUP,
            0,
        )

        relegation = skipped_competitions.get(
            ScheduleCompetition.RELEGATION,
            0,
        )

        unknown_count = skipped_competitions.get(
            ScheduleCompetition.UNKNOWN,
            0,
        )

        print(f"  Pokal ignoriert:          {cup_count}")
        print(f"  Relegation ignoriert:          {relegation}")
        print(f"  Unbekannter Wettbewerb:   {unknown_count}")

    # =========================================================================
    # Meeting-Dispatcher
    # =========================================================================

    def _sync_meeting(
        self,
        session: Session,
        season: Season,
        meeting: dict,
    ) -> tuple[str, ScheduleCompetition]:

        competition = self._get_competition_type(meeting)

        # ---------------------------------------------------------------------
        # Normale Punktrunde
        # ---------------------------------------------------------------------

        if competition == ScheduleCompetition.LEAGUE:
            action = self._sync_league_meeting(
                session=session,
                season=season,
                meeting=meeting,
            )

            return (
                action,
                competition,
            )

        # ---------------------------------------------------------------------
        # Pokal und Relegation
        #
        # Wird aktuell bewusst NICHT importiert.
        #
        # Später kann hier einfach ergänzt werden:
        #
        # if competition == ScheduleCompetition.CUP:
        #
        #     action = self._sync_cup_meeting(...)
        #
        #     return action, competition
        #
        # Dadurch bleibt die Liga-Logik vollständig getrennt.
        # ---------------------------------------------------------------------

        if competition == ScheduleCompetition.CUP:
            return (
                "unsupported",
                competition,
            )

        if competition == ScheduleCompetition.RELEGATION:
            return (
                "unsupported",
                competition,
            )

        # ---------------------------------------------------------------------
        # Unbekannter round_type
        #
        # Nicht blind importieren.
        #
        # So verhindern wir, dass eine zukünftige myTT-Wettbewerbsart
        # versehentlich als normale Liga behandelt wird.
        # ---------------------------------------------------------------------

        return (
            "unsupported",
            ScheduleCompetition.UNKNOWN,
        )

    # =========================================================================
    # Wettbewerbsart bestimmen
    # =========================================================================

    @staticmethod
    def _get_competition_type(
        meeting: dict,
    ) -> ScheduleCompetition:

        round_type = str(
            meeting.get(
                "round_type",
                "",
            )
        ).strip()

        return ROUND_TYPE_COMPETITION_MAP.get(
            round_type,
            ScheduleCompetition.UNKNOWN,
        )

    # =========================================================================
    # Season
    # =========================================================================

    def _get_or_create_season(
        self,
        session: Session,
        start_year: int,
        end_year: int,
        half: SeasonHalf,
    ) -> Season:

        statement = select(Season).where(
            Season.start_year == start_year,
            Season.end_year == end_year,
            Season.half == half,
        )

        season = session.exec(statement).first()

        # ---------------------------------------------------------------------
        # Bereits vorhanden
        # ---------------------------------------------------------------------

        if season is not None:
            return season

        # ---------------------------------------------------------------------
        # Neu anlegen
        # ---------------------------------------------------------------------

        season = Season(
            start_year=start_year,
            end_year=end_year,
            half=half,
        )

        session.add(season)

        session.flush()

        print(
            f"  Season neu angelegt: "
            f"{start_year}/{str(end_year)[-2:]} "
            f"{half.value.upper()}"
        )

        return season

    # =========================================================================
    # Ligabegegnung synchronisieren
    # =========================================================================

    def _sync_league_meeting(
        self,
        session: Session,
        season: Season,
        meeting: dict,
    ) -> str:

        meeting_id = int(meeting["meeting_id"])

        # =====================================================================
        # Eigenes Team ermitteln
        # =====================================================================

        (
            mytt_team_id,
            team_name,
            is_home,
        ) = self._get_own_team_data(meeting)

        # =====================================================================
        # LeagueGroup zuerst anlegen / aktualisieren
        #
        # Das passiert bewusst VOR dem Team.
        #
        # Dadurch können wir auf einer komplett leeren Datenbank auch
        # historische Teams direkt aus dem Schedule erzeugen.
        # =====================================================================

        league_group = self._upsert_league_group(
            session=session,
            season=season,
            meeting=meeting,
        )

        # =====================================================================
        # Team suchen
        # =====================================================================

        team = session.exec(
            select(Team).where(
                Team.season_id == season.id,
                Team.mytt_team_id == mytt_team_id,
            )
        ).first()

        # =====================================================================
        # Historisches Team anlegen
        # =====================================================================

        if team is None:
            team = Team(
                season_id=season.id,
                league_group_id=(league_group.id),
                mytt_team_id=(mytt_team_id),
                name=(team_name),
                # Die Mannschaftsnummer kann aus dem Schedule
                # nicht zuverlässig bestimmt werden.
                #
                # Sie wird später durch RegistrationsSync
                # aus der offiziellen Mannschaftsmeldung ergänzt.
                team_number=None,
            )

            session.add(team)

            session.flush()

            print(f"  Team neu angelegt: {team_name} ({mytt_team_id})")

        # =====================================================================
        # Bestehendes Team aktualisieren
        # =====================================================================

        else:
            # -----------------------------------------------------------------
            # Vollständigen Teamnamen aus Schedule übernehmen
            #
            # Teams-API:
            #
            #   Erwachsene III
            #
            # Schedule:
            #
            #   TTC Langen-Brombach III
            # -----------------------------------------------------------------

            team.name = team_name

            # -----------------------------------------------------------------
            # Ligazugehörigkeit aktuell halten
            # -----------------------------------------------------------------

            team.league_group_id = league_group.id

        # =====================================================================
        # Gegner bestimmen
        # =====================================================================

        if is_home:
            opponent_name = meeting["team_away"].strip()

        else:
            opponent_name = meeting["team_home"].strip()

        # =====================================================================
        # Status / Ergebnis
        # =====================================================================

        is_complete = bool(
            meeting.get(
                "is_meeting_complete",
                False,
            )
        )

        if is_complete:
            if is_home:
                score_ttc = self._to_int(meeting.get("matches_won"))

                score_opponent = self._to_int(meeting.get("matches_lost"))

            else:
                score_ttc = self._to_int(meeting.get("matches_lost"))

                score_opponent = self._to_int(meeting.get("matches_won"))

        else:
            # -----------------------------------------------------------------
            # myTT liefert für geplante Spiele häufig 0:0.
            #
            # Das soll nicht als echtes Ergebnis gespeichert werden.
            # -----------------------------------------------------------------

            score_ttc = None
            score_opponent = None

        # =====================================================================
        # Ort
        # =====================================================================

        location = meeting.get("location") or {}

        # =====================================================================
        # Termine einmal zentral parsen
        # =====================================================================

        new_scheduled_at = self._require_datetime(
            value=meeting.get("date"),
            field_name="date",
            meeting_id=meeting_id,
        )

        incoming_original_scheduled_at = self._parse_datetime(
            meeting.get("original_date")
        )

        new_ended_at = self._parse_datetime(meeting.get("end_date"))

        # =====================================================================
        # TeamMatch suchen
        # =====================================================================

        team_match = session.exec(
            select(TeamMatch).where(TeamMatch.mytt_meeting_id == meeting_id)
        ).first()

        # =====================================================================
        # Neue Begegnung
        # =====================================================================

        if team_match is None:
            team_match = TeamMatch(
                team_id=team.id,
                mytt_meeting_id=meeting_id,
                opponent_name=opponent_name,
                is_home=is_home,
                is_completed=is_complete,
                scheduled_at=new_scheduled_at,
                original_scheduled_at=incoming_original_scheduled_at,
                status=meeting.get(
                    "state",
                    "unknown",
                ),
                venue_name=location.get("label"),
                venue_street=location.get("street"),
                venue_city=location.get("city"),
                score_ttc=score_ttc,
                score_opponent=score_opponent,
            )

            session.add(team_match)

            action = "created"

        # =====================================================================
        # Vorhandene Begegnung
        # =====================================================================

        else:
            # -----------------------------------------------------------------
            # Aktuellen bisher bekannten Termin merken,
            # bevor wir ihn überschreiben.
            # -----------------------------------------------------------------

            old_scheduled_at = team_match.scheduled_at

            # =================================================================
            # Ursprünglichen Termin behandeln
            # =================================================================

            if incoming_original_scheduled_at is not None:
                # -------------------------------------------------------------
                # myTT liefert selbst einen ursprünglichen Termin.
                #
                # Dieser ist die bevorzugte Quelle.
                # -------------------------------------------------------------

                team_match.original_scheduled_at = incoming_original_scheduled_at

            elif (
                old_scheduled_at is not None
                and old_scheduled_at != new_scheduled_at
                and team_match.original_scheduled_at is None
            ):
                # -------------------------------------------------------------
                # myTT liefert kein original_date,
                # aber der Termin hat sich gegenüber unserer DB geändert.
                #
                # Damit erkennen wir die Verlegung selbst und verlieren
                # den ursprünglichen Termin nicht.
                # -------------------------------------------------------------

                team_match.original_scheduled_at = old_scheduled_at

            # =================================================================
            # Aktuellen Termin aktualisieren
            # =================================================================

            team_match.scheduled_at = new_scheduled_at

            # =================================================================
            # Restliche Begegnungsdaten aktualisieren
            # =================================================================

            team_match.team_id = team.id

            team_match.opponent_name = opponent_name

            team_match.is_home = is_home

            team_match.status = meeting.get(
                "state",
                team_match.status,
            )

            team_match.venue_name = location.get("label")

            team_match.venue_street = location.get("street")

            team_match.venue_city = location.get("city")

            team_match.score_ttc = score_ttc

            team_match.score_opponent = score_opponent

            # -----------------------------------------------------------------
            # WICHTIG:
            #
            # details_imported_at wird hier bewusst NICHT verändert.
            #
            # Der ScheduleSync ist nur für Begegnungs-Metadaten zuständig.
            #
            # Match / MatchParticipant / SetResult usw. werden später
            # vom MeetingSync verwaltet.
            # -----------------------------------------------------------------

            action = "updated"

        # =====================================================================
        # ID wird für Notices benötigt
        # =====================================================================

        session.flush()

        # =====================================================================
        # Notices synchronisieren
        # =====================================================================

        self._sync_notices(
            session=session,
            team_match=team_match,
            meeting=meeting,
        )

        return action

    # =========================================================================
    # LeagueGroup
    # =========================================================================

    def _upsert_league_group(
        self,
        session: Session,
        season: Season,
        meeting: dict,
    ) -> LeagueGroup:

        mytt_group_id = int(meeting["league_id"])

        # ---------------------------------------------------------------------
        # Wichtig:
        #
        # Den ursprünglichen String behalten.
        #
        # Beispiel:
        #
        # " Bezirksklasse Gr. 3"
        # ---------------------------------------------------------------------

        raw_league_name = meeting["league_name"]

        # ---------------------------------------------------------------------
        # Für die normale Anzeige / DB wollen wir einen sauberen Namen.
        # ---------------------------------------------------------------------

        league_name = raw_league_name.strip()

        # ---------------------------------------------------------------------
        # Der technische URL-Gruppenname von myTT entsteht bei den bisher
        # beobachteten Daten durch Ersetzen der Leerzeichen mit "_".
        #
        # Beispiel:
        #
        # " Bezirksklasse Gr. 3"
        #
        # ->
        #
        # "_Bezirksklasse_Gr._3"
        # ---------------------------------------------------------------------

        mytt_slug = self._build_group_slug(raw_league_name)

        statement = select(LeagueGroup).where(
            LeagueGroup.season_id == season.id,
            LeagueGroup.mytt_group_id == mytt_group_id,
        )

        league_group = session.exec(statement).first()

        # =====================================================================
        # Vorhandene Gruppe aktualisieren
        # =====================================================================

        if league_group is not None:
            league_group.name = league_name

            league_group.mytt_slug = mytt_slug

            return league_group

        # =====================================================================
        # Neue Gruppe anlegen
        # =====================================================================

        league_group = LeagueGroup(
            season_id=season.id,
            mytt_group_id=(mytt_group_id),
            name=(league_name),
            mytt_slug=(mytt_slug),
        )

        session.add(league_group)

        session.flush()

        return league_group

    # =========================================================================
    # Eigenes Team bestimmen
    # =========================================================================

    def _get_own_team_data(
        self,
        meeting: dict,
    ) -> tuple[int, str, bool]:

        club_number = str(settings.mytt_club_number)

        # =====================================================================
        # Heim
        # =====================================================================

        if str(meeting["team_home_club_id"]) == club_number:
            return (
                int(meeting["team_home_id"]),
                meeting["team_home"].strip(),
                True,
            )

        # =====================================================================
        # Auswärts
        # =====================================================================

        if str(meeting["team_away_club_id"]) == club_number:
            return (
                int(meeting["team_away_id"]),
                meeting["team_away"].strip(),
                False,
            )

        raise ValueError(
            f"Meeting {meeting['meeting_id']} gehört nicht zum eigenen Verein."
        )

    # =========================================================================
    # Notices
    # =========================================================================

    def _sync_notices(
        self,
        session: Session,
        team_match: TeamMatch,
        meeting: dict,
    ) -> None:

        for (
            code,
            (
                flag_field,
                info_field,
            ),
        ) in NOTICE_FIELDS.items():
            is_active = bool(meeting.get(flag_field))

            existing_notice = session.exec(
                select(TeamMatchNotice).where(
                    TeamMatchNotice.team_match_id == team_match.id,
                    TeamMatchNotice.code == code,
                )
            ).first()

            # =================================================================
            # Notice aktuell vorhanden
            # =================================================================

            if is_active:
                info = meeting.get(info_field) if info_field else None

                # -------------------------------------------------------------
                # Neues Notice
                # -------------------------------------------------------------

                if existing_notice is None:
                    notice = TeamMatchNotice(
                        team_match_id=(team_match.id),
                        code=code,
                        info=info,
                    )

                    session.add(notice)

                # -------------------------------------------------------------
                # Notice aktualisieren
                # -------------------------------------------------------------

                else:
                    existing_notice.info = info

            # =================================================================
            # Notice wurde bei myTT wieder entfernt
            # =================================================================

            elif existing_notice is not None:
                session.delete(existing_notice)

    # =========================================================================
    # myTT-Saisonname
    # =========================================================================

    @staticmethod
    def _build_mytt_season_name(
        start_year: int,
        end_year: int,
    ) -> str:

        # ---------------------------------------------------------------------
        # click-TT URL:
        #
        # 2026/27
        #     ↓
        # 26--27
        # ---------------------------------------------------------------------

        return f"{str(start_year)[-2:]}--{str(end_year)[-2:]}"

    # =========================================================================
    # Zeitraum der Halbserie
    # =========================================================================

    @staticmethod
    def _get_period(
        start_year: int,
        end_year: int,
        half: SeasonHalf,
    ) -> tuple[date, date]:

        if end_year != start_year + 1:
            raise ValueError("end_year muss start_year + 1 sein.")

        # =====================================================================
        # Vorrunde
        # =====================================================================

        if half == SeasonHalf.VR:
            return (
                date(
                    start_year,
                    7,
                    1,
                ),
                date(
                    start_year,
                    12,
                    31,
                ),
            )

        # =====================================================================
        # Rückrunde
        # =====================================================================

        if half == SeasonHalf.RR:
            return (
                date(
                    end_year,
                    1,
                    1,
                ),
                date(
                    end_year,
                    6,
                    30,
                ),
            )

        raise ValueError(f"Unbekannte Halbserie: {half}")

    # =========================================================================
    # Integer
    # =========================================================================

    @staticmethod
    def _to_int(
        value,
    ) -> int | None:

        if value is None:
            return None

        return int(value)

    # =========================================================================
    # Datetime
    # =========================================================================

    @staticmethod
    def _parse_datetime(
        value,
    ) -> datetime | None:

        if not value:
            return None

        return datetime.fromisoformat(value)

    # =========================================================================
    # LeagueGroup-Slug
    # =========================================================================

    @staticmethod
    def _build_group_slug(
        league_name: str,
    ) -> str:

        return league_name.replace(
            " ",
            "_",
        )

    # =========================================================================
    # Pflicht-Datetime
    # =========================================================================

    @classmethod
    def _require_datetime(
        cls,
        value,
        field_name: str,
        meeting_id: int,
    ) -> datetime:

        parsed = cls._parse_datetime(value)

        if parsed is None:
            raise ValueError(f"Meeting {meeting_id}: Pflichtfeld '{field_name}' fehlt.")

        return parsed
