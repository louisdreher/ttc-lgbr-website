import asyncio
import json
from datetime import date

import httpx
from sqlmodel import Session, select

from app.integrations.mytischtennis.sync.league_table import (
    LeagueTableSync,
)
from app.integrations.mytischtennis.sync.meeting import (
    MeetingSync,
)
from app.integrations.mytischtennis.sync.registrations import (
    RegistrationsSync,
)
from app.integrations.mytischtennis.sync.schedule import (
    ScheduleSync,
)
from backend.app.core.database import engine
from backend.app.domains.competition.league.model import LeagueGroup
from backend.app.domains.competition.matches.models import TeamMatch
from backend.app.domains.competition.season.model import Season, SeasonHalf
from backend.app.domains.competition.teams.model import Team

# ---------------------------------------------------------------------------
# Allgemeine Pause zwischen mehreren myTT-Requests
# ---------------------------------------------------------------------------

REQUEST_DELAY = 1.0


# ---------------------------------------------------------------------------
# Retry-Einstellungen für Mannschaftsmeldungen
# ---------------------------------------------------------------------------

REGISTRATION_MAX_ATTEMPTS = 3

REGISTRATION_RETRY_DELAY = 3.0


class CurrentSeasonSync:
    def __init__(self):
        self.schedule_sync = ScheduleSync()

        self.meeting_sync = MeetingSync()

        self.registration_sync = RegistrationsSync()

        self.league_table_sync = LeagueTableSync()

    # =========================================================================
    # Schedule
    # =========================================================================

    async def sync_schedule(self) -> int:
        """
        Synchronisiert den Schedule der aktuell laufenden Halbserie.

        Gibt anschließend die interne Season-ID zurück.
        """

        start_year, end_year, half = self._get_current_season()

        print()
        print("=" * 70)
        print("CURRENT SCHEDULE SYNC")
        print("=" * 70)

        print(f"Saison: {start_year}/{str(end_year)[-2:]} {half.value.upper()}")

        await self.schedule_sync.sync(
            start_year=start_year,
            end_year=end_year,
            half=half,
        )

        return self._get_season_id(
            start_year=start_year,
            end_year=end_year,
            half=half,
        )

    # =========================================================================
    # Neue abgeschlossene Meetings
    # =========================================================================

    async def sync_new_meetings(self) -> None:
        """
        Aktualisiert zuerst den Schedule.

        Anschließend werden nur Begegnungen geladen, die:

        - abgeschlossen sind
        - noch keine importierten Detaildaten besitzen
        """

        print()
        print("=" * 70)
        print("CURRENT MEETING SYNC")
        print("=" * 70)

        # ---------------------------------------------------------------------
        # Vor der Suche nach neuen Spielen immer zuerst den Schedule laden.
        #
        # Dadurch wird insbesondere is_completed aktualisiert.
        # ---------------------------------------------------------------------

        season_id = await self.sync_schedule()

        team_match_ids = self._get_pending_team_match_ids(
            season_id=season_id,
        )

        print()
        print(f"{len(team_match_ids)} neue abgeschlossene Begegnungen gefunden.")

        imported = 0
        skipped = 0
        failed = 0

        for index, team_match_id in enumerate(
            team_match_ids,
            start=1,
        ):
            print()
            print(f"[{index}/{len(team_match_ids)}] TeamMatch {team_match_id}")

            try:
                result = await self.meeting_sync.sync(
                    team_match_id=team_match_id,
                )

                if result:
                    imported += 1

                else:
                    skipped += 1

            except Exception as exc:
                failed += 1

                print(f"  FEHLER: {type(exc).__name__}: {exc}")

            if index < len(team_match_ids):
                await asyncio.sleep(REQUEST_DELAY)

        print()
        print("=" * 70)
        print("MEETING SYNC ABGESCHLOSSEN")
        print("=" * 70)

        print(f"Importiert:     {imported}")
        print(f"Übersprungen:   {skipped}")
        print(f"Fehlgeschlagen: {failed}")

    # =========================================================================
    # Ligatabellen
    # =========================================================================

    async def sync_league_tables(self) -> None:
        """
        Aktualisiert alle Ligatabellen der aktuellen Halbserie.

        Dieser Sync kann später z. B. einmal täglich ausgeführt werden.
        """

        print()
        print("=" * 70)
        print("CURRENT LEAGUE TABLE SYNC")
        print("=" * 70)

        # ---------------------------------------------------------------------
        # Schedule vorher aktualisieren.
        #
        # Dadurch sind alle aktuellen LeagueGroups und Teams bekannt.
        # ---------------------------------------------------------------------

        season_id = await self.sync_schedule()

        league_group_ids = self._get_league_group_ids(
            season_id=season_id,
        )

        print()
        print(f"{len(league_group_ids)} LeagueGroups gefunden.")

        successful = 0
        skipped = 0
        failed = 0

        for index, league_group_id in enumerate(
            league_group_ids,
            start=1,
        ):
            print()
            print(f"[{index}/{len(league_group_ids)}] LeagueGroup {league_group_id}")

            try:
                result = await self.league_table_sync.sync(
                    league_group_id=league_group_id,
                )

                if result:
                    successful += 1

                else:
                    skipped += 1

            except Exception as exc:
                failed += 1

                print(f"  FEHLER: {type(exc).__name__}: {exc}")

            if index < len(league_group_ids):
                await asyncio.sleep(REQUEST_DELAY)

        print()
        print("=" * 70)
        print("LEAGUE TABLE SYNC ABGESCHLOSSEN")
        print("=" * 70)

        print(f"Erfolgreich:    {successful}")
        print(f"Übersprungen:   {skipped}")
        print(f"Fehlgeschlagen: {failed}")

    # =========================================================================
    # Mannschaftsmeldungen
    # =========================================================================

    async def sync_registrations(self) -> None:
        """
        Aktualisiert die Mannschaftsmeldungen der aktuellen Halbserie.

        Dieser Sync muss während einer laufenden Halbserie nur gelegentlich
        ausgeführt werden.
        """

        print()
        print("=" * 70)
        print("CURRENT REGISTRATIONS SYNC")
        print("=" * 70)

        # ---------------------------------------------------------------------
        # Schedule zuerst aktualisieren.
        #
        # RegistrationsSync setzt voraus, dass Season, LeagueGroup und Team
        # bereits existieren.
        # ---------------------------------------------------------------------

        season_id = await self.sync_schedule()

        league_group_ids = self._get_league_group_ids(
            season_id=season_id,
        )

        print()
        print(f"{len(league_group_ids)} LeagueGroups gefunden.")

        successful = 0
        skipped = 0
        failed = 0

        for index, league_group_id in enumerate(
            league_group_ids,
            start=1,
        ):
            print()
            print(f"[{index}/{len(league_group_ids)}] LeagueGroup {league_group_id}")

            try:
                result = await self._sync_registration_with_retry(
                    league_group_id=league_group_id,
                )

                if result:
                    successful += 1

                else:
                    skipped += 1

            except Exception as exc:
                failed += 1

                print(f"  FEHLER: {type(exc).__name__}: {exc}")

            if index < len(league_group_ids):
                await asyncio.sleep(REQUEST_DELAY)

        print()
        print("=" * 70)
        print("REGISTRATIONS SYNC ABGESCHLOSSEN")
        print("=" * 70)

        print(f"Erfolgreich:    {successful}")
        print(f"Übersprungen:   {skipped}")
        print(f"Fehlgeschlagen: {failed}")

    # =========================================================================
    # Mannschaftsmeldung mit Retry
    # =========================================================================

    async def _sync_registration_with_retry(
        self,
        league_group_id: int,
    ) -> bool:
        """
        Führt den RegistrationsSync mit Retry für bekannte temporäre
        myTischtennis-Fehler aus.

        Erneut versucht werden:

        - HTTP 403
        - HTTP 408
        - HTTP 429
        - HTTP 5xx
        - Verbindungsfehler
        - ungültige JSON-Antworten

        Andere HTTP-Fehler werden direkt weitergegeben.
        """

        for attempt in range(
            1,
            REGISTRATION_MAX_ATTEMPTS + 1,
        ):
            try:
                return await self.registration_sync.sync(
                    league_group_id=league_group_id,
                )

            # -----------------------------------------------------------------
            # HTTP-Statusfehler
            # -----------------------------------------------------------------

            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code

                retryable = (
                    status_code
                    in {
                        403,
                        408,
                        429,
                    }
                    or 500 <= status_code <= 599
                )

                if not retryable:
                    raise

                print(
                    f"  Temporärer HTTP-Fehler "
                    f"{status_code} "
                    f"(Versuch "
                    f"{attempt}/"
                    f"{REGISTRATION_MAX_ATTEMPTS})"
                )

                print(f"  URL: {exc.request.url}")

                if attempt >= REGISTRATION_MAX_ATTEMPTS:
                    raise

            # -----------------------------------------------------------------
            # Verbindungsfehler
            # -----------------------------------------------------------------

            except httpx.RequestError as exc:
                print(
                    f"  Temporärer Verbindungsfehler "
                    f"(Versuch "
                    f"{attempt}/"
                    f"{REGISTRATION_MAX_ATTEMPTS})"
                )

                print(f"  {type(exc).__name__}: {exc}")

                if attempt >= REGISTRATION_MAX_ATTEMPTS:
                    raise

            # -----------------------------------------------------------------
            # Ungültige JSON-Antwort
            # -----------------------------------------------------------------

            except json.JSONDecodeError as exc:
                print(
                    f"  Ungültige JSON-Antwort "
                    f"(Versuch "
                    f"{attempt}/"
                    f"{REGISTRATION_MAX_ATTEMPTS})"
                )

                print(f"  {type(exc).__name__}: {exc}")

                if attempt >= REGISTRATION_MAX_ATTEMPTS:
                    raise

            # -----------------------------------------------------------------
            # Vor erneutem Request warten
            # -----------------------------------------------------------------

            print(f"  Neuer Versuch in {REGISTRATION_RETRY_DELAY} Sekunden ...")

            await asyncio.sleep(REGISTRATION_RETRY_DELAY)

        # Sollte durch die Schleifenlogik eigentlich nie erreicht werden.
        return False

    # =========================================================================
    # Noch nicht importierte abgeschlossene Begegnungen
    # =========================================================================

    @staticmethod
    def _get_pending_team_match_ids(
        season_id: int,
    ) -> list[int]:
        """
        Liefert ausschließlich abgeschlossene Begegnungen der aktuellen
        Halbserie, deren Meeting-Details noch nicht importiert wurden.
        """

        with Session(engine) as session:
            team_matches = session.exec(
                select(TeamMatch)
                .join(
                    Team,
                    Team.id == TeamMatch.team_id,
                )
                .where(
                    Team.season_id == season_id,
                    TeamMatch.is_completed.is_(True),
                    TeamMatch.details_imported_at.is_(None),
                )
                .order_by(TeamMatch.scheduled_at)
            ).all()

            return [
                team_match.id
                for team_match in team_matches
                if team_match.id is not None
            ]

    # =========================================================================
    # LeagueGroups der aktuellen Halbserie
    # =========================================================================

    @staticmethod
    def _get_league_group_ids(
        season_id: int,
    ) -> list[int]:

        with Session(engine) as session:
            league_groups = session.exec(
                select(LeagueGroup)
                .where(LeagueGroup.season_id == season_id)
                .order_by(LeagueGroup.id)
            ).all()

            return [
                league_group.id
                for league_group in league_groups
                if league_group.id is not None
            ]

    # =========================================================================
    # Season-ID bestimmen
    # =========================================================================

    @staticmethod
    def _get_season_id(
        start_year: int,
        end_year: int,
        half: SeasonHalf,
    ) -> int:

        with Session(engine) as session:
            season = session.exec(
                select(Season).where(
                    Season.start_year == start_year,
                    Season.end_year == end_year,
                    Season.half == half,
                )
            ).first()

            if season is None:
                raise RuntimeError(
                    "Season nicht gefunden: "
                    f"{start_year}/{end_year} "
                    f"{half.value.upper()}"
                )

            if season.id is None:
                raise RuntimeError("Season besitzt keine ID.")

            return season.id

    # =========================================================================
    # Aktuelle Halbserie
    # =========================================================================

    @staticmethod
    def _get_current_season() -> tuple[
        int,
        int,
        SeasonHalf,
    ]:
        """
        Bestimmt anhand des aktuellen Datums die laufende Halbserie.

        Januar - Juni:
            Rückrunde der im Vorjahr begonnenen Saison.

        Juli - Dezember:
            Vorrunde der neu begonnenen Saison.
        """

        today = date.today()

        # ---------------------------------------------------------------------
        # Januar bis Juni
        #
        # Beispiel:
        #
        # März 2027
        # -> Saison 2026/27 RR
        # ---------------------------------------------------------------------

        if today.month <= 6:
            return (
                today.year - 1,
                today.year,
                SeasonHalf.RR,
            )

        # ---------------------------------------------------------------------
        # Juli bis Dezember
        #
        # Beispiel:
        #
        # September 2026
        # -> Saison 2026/27 VR
        # ---------------------------------------------------------------------

        return (
            today.year,
            today.year + 1,
            SeasonHalf.VR,
        )
