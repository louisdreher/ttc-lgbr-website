from datetime import date
from typing import Any, Literal
from urllib.parse import quote

import httpx

from app.core.settings import settings

RoundFilter = Literal["gesamt", "vr", "rr"]


class MyTischtennisClient:
    def __init__(self):
        self.base_url = str(settings.mytt_base_url).rstrip("/")
        self.timeout = 20.0

    # -------------------------------------------------------------------------
    # Interne Request-Hilfe
    # -------------------------------------------------------------------------

    async def _get_json(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict:

        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            follow_redirects=True,
        ) as client:
            response = await client.get(
                endpoint,
                params=params,
            )

            if response.status_code == 429:
                raise RuntimeError("myTischtennis Rate Limit erreicht.")

            response.raise_for_status()

            return response.json()

    # =========================================================================
    # VEREIN
    # =========================================================================

    async def get_club_schedule_data(
        self,
        date_start: date,
        date_end: date,
        season: str = "26--27",
    ) -> dict:
        """
        Lädt den Vereins-Spielplan für einen Datumsbereich.

        Dieser Remix-Loader eignet sich besonders für den historischen Import,
        da date_start und date_end frei angegeben werden können.
        """

        endpoint = (
            f"/click-tt/"
            f"{settings.mytt_organization}/"
            f"{season}/"
            f"verein/"
            f"{settings.mytt_club_number}/"
            f"{settings.mytt_club_slug}/"
            f"spielplan"
        )

        params = {
            "date_start": date_start.isoformat(),
            "date_end": date_end.isoformat(),
            "_data": (
                "routes/click-tt+/"
                "$association+/"
                "$season+/"
                "verein.$clubid.$clubname+/"
                "spielplan"
            ),
        }

        return await self._get_json(
            endpoint=endpoint,
            params=params,
        )

    async def get_current_teams(self) -> dict:
        """
        Lädt die aktuell bei myTischtennis geführten Mannschaften
        unseres Vereins.

        Achtung:
        Dieser API-Endpunkt besitzt keinen season-Parameter und ist daher
        primär für die aktuelle Saison gedacht.
        """

        endpoint = "/api/ttr/teams"

        params = {
            "clubNumber": str(settings.mytt_club_number),
            "organization": settings.mytt_organization,
        }

        return await self._get_json(
            endpoint=endpoint,
            params=params,
        )

    async def get_club_teams_data(
        self,
        season: str,
    ) -> dict:
        """
        Lädt die Mannschaftsseite eines Vereins über den Remix-Loader.

        Kann sinnvoll sein, wenn wir Daten benötigen, die
        /api/ttr/teams nicht liefert.
        """

        endpoint = (
            f"/click-tt/"
            f"{settings.mytt_organization}/"
            f"{season}/"
            f"verein/"
            f"{settings.mytt_club_number}/"
            f"{settings.mytt_club_slug}/"
            f"mannschaften"
        )

        params = {
            "_data": (
                "routes/click-tt+/"
                "$association+/"
                "$season+/"
                "verein.$clubid.$clubname+/"
                "mannschaften"
            ),
        }

        return await self._get_json(
            endpoint=endpoint,
            params=params,
        )

    # =========================================================================
    # MANNSCHAFT
    # =========================================================================

    async def get_team_players(
        self,
        team_id: int,
    ) -> dict:
        """
        Lädt die gemeldeten Spieler einer Mannschaft.

        Liefert unter anderem:
        - Vorname
        - Nachname
        - NUID
        - Rangposition
        """

        endpoint = "/api/ttr/team/players"

        params = {
            "teamId": str(team_id),
        }

        return await self._get_json(
            endpoint=endpoint,
            params=params,
        )

    async def get_team_schedule(
        self,
        team_id: int,
        season: str,
    ) -> dict:
        """
        Lädt den Spielplan einer Mannschaft über den einfachen API-Endpunkt.
        """

        endpoint = "/api/ttr/team/schedule"

        params = {
            "teamId": str(team_id),
            "season": season,
        }

        return await self._get_json(
            endpoint=endpoint,
            params=params,
        )

    async def get_team_schedule_data(
        self,
        season: str,
        league_slug: str,
        group_id: int,
        team_id: int,
        team_name: str,
        round_filter: RoundFilter = "gesamt",
    ) -> dict:
        """
        Lädt den ausführlichen Mannschaftsspielplan über den click-TT
        Remix-Loader.

        round_filter:
        - gesamt
        - vr
        - rr
        """

        endpoint = (
            f"/click-tt/"
            f"{settings.mytt_organization}/"
            f"{season}/"
            f"ligen/"
            f"{league_slug}/"
            f"gruppe/"
            f"{group_id}/"
            f"mannschaft/"
            f"{team_id}/"
            f"{team_name}/"
            f"spielplan/"
            f"{round_filter}"
        )

        params = {
            "_data": (
                "routes/click-tt+/"
                "$association+/"
                "$season+/"
                "$type+/"
                "($groupname).gruppe.$urlid_."
                "mannschaft.$teamid.$teamname+/"
                "spielplan.$filter"
            ),
        }

        return await self._get_json(
            endpoint=endpoint,
            params=params,
        )

    async def get_team_player_balances(
        self,
        season: str,
        league_slug: str,
        group_id: int,
        team_id: int,
        team_name: str,
        round_filter: RoundFilter = "gesamt",
    ) -> dict:
        """
        Lädt die Spielerbilanzen einer Mannschaft.

        Enthält zusätzlich die vollständige Ligatabelle
        unter tableData.table.
        """

        encoded_league_slug = quote(
            league_slug,
            safe="",
        )

        encoded_team_name = quote(
            team_name,
            safe="",
        )

        endpoint = (
            f"/click-tt/"
            f"{settings.mytt_organization}/"
            f"{season}/"
            f"ligen/"
            f"{encoded_league_slug}/"
            f"gruppe/"
            f"{group_id}/"
            f"mannschaft/"
            f"{team_id}/"
            f"{encoded_team_name}/"
            f"spielerbilanzen/"
            f"{round_filter}"
        )

        params = {
            "_data": (
                "routes/click-tt+/"
                "$association+/"
                "$season+/"
                "$type+/"
                "($groupname).gruppe.$urlid_."
                "mannschaft.$teamid.$teamname+/"
                "spielerbilanzen.$filter"
            ),
        }

        return await self._get_json(
            endpoint=endpoint,
            params=params,
        )

    async def get_team_info(
        self,
        season: str,
        league_slug: str,
        group_id: int,
        team_id: int,
        team_name: str,
    ) -> dict:
        """
        Lädt weitere Informationen zu einer Mannschaft.

        Kann beispielsweise Spiellokal, Mannschaftskontakt
        oder Mannschaftsfoto enthalten.
        """

        endpoint = (
            f"/click-tt/"
            f"{settings.mytt_organization}/"
            f"{season}/"
            f"ligen/"
            f"{league_slug}/"
            f"gruppe/"
            f"{group_id}/"
            f"mannschaft/"
            f"{team_id}/"
            f"{team_name}/"
            f"infos"
        )

        params = {
            "_data": (
                "routes/click-tt+/"
                "$association+/"
                "$season+/"
                "$type+/"
                "($groupname).gruppe.$urlid_."
                "mannschaft.$teamid.$teamname+/"
                "infos"
            ),
        }

        return await self._get_json(
            endpoint=endpoint,
            params=params,
        )

    # =========================================================================
    # BEGEGNUNG
    # =========================================================================

    async def get_meeting(
        self,
        meeting_id: int,
    ) -> dict:
        """
        Lädt die Detaildaten einer Begegnung.

        Enthält bei verfügbaren Daten unter anderem:
        - Aufstellungen
        - Einzel/Doppel
        - Spieler
        - Satzstände
        - Gesamtergebnis
        """

        endpoint = f"/api/meeting/{meeting_id}/live"

        return await self._get_json(
            endpoint=endpoint,
        )

    # =========================================================================
    # LIGA / GRUPPE
    # =========================================================================

    async def get_league_table(
        self,
        group_id: int,
        association: str | None = None,
    ) -> dict:
        """
        Lädt die Tabelle einer Liga/Gruppe.
        """

        association = association or settings.mytt_organization

        endpoint = f"/api/league-table/{association}/{group_id}"

        return await self._get_json(
            endpoint=endpoint,
        )

    # =========================================================================
    # Mannschaftsmeldung
    # =========================================================================

    async def get_team_registrations(
        self,
        season: str,
        league_slug: str,
        group_id: int,
        round_filter: str,
    ) -> dict:

        encoded_league_slug = quote(
            league_slug,
            safe="",
        )

        endpoint = (
            f"/click-tt/{settings.mytt_organization}/{season}/"
            f"ligen/{encoded_league_slug}/gruppe/{group_id}/"
            f"mannschaftsmeldungen/{round_filter}"
        )

        params = {
            "_data": (
                "routes/click-tt+/"
                "$association+/"
                "$season+/"
                "$type+/"
                "$groupname.gruppe.$urlid+/"
                "mannschaftsmeldungen.$filter"
            )
        }

        return await self._get_json(
            endpoint=endpoint,
            params=params,
        )
