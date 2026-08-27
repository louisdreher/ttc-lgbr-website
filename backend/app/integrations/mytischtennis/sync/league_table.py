from app.integrations.mytischtennis.api import MyTischtennisClient
from sqlmodel import Session, select

from backend.app.core.database import engine
from backend.app.domains.competition.league.model import LeagueGroup, LeagueTableEntry
from backend.app.domains.competition.season.model import Season, SeasonHalf
from backend.app.domains.competition.teams.model import Team


class LeagueTableSync:
    def __init__(self):
        self.client = MyTischtennisClient()

    # -------------------------------------------------------------------------
    # Öffentlicher Einstieg
    # -------------------------------------------------------------------------

    async def sync(
        self,
        league_group_id: int,
    ) -> bool:

        # ---------------------------------------------------------------------
        # Benötigte Informationen aus der DB holen.
        #
        # Die DB-Session bleibt bewusst nicht während des HTTP-Requests offen.
        # ---------------------------------------------------------------------

        with Session(engine) as session:
            league_group = session.get(
                LeagueGroup,
                league_group_id,
            )

            if league_group is None:
                raise ValueError(f"LeagueGroup {league_group_id} existiert nicht.")

            season = session.get(
                Season,
                league_group.season_id,
            )

            if season is None:
                raise RuntimeError(f"Season {league_group.season_id} existiert nicht.")

            # -----------------------------------------------------------------
            # Wir brauchen eine eigene Mannschaft dieser Gruppe,
            # um den API-Endpunkt aufzurufen.
            #
            # Die Tabelle selbst gilt anschließend für die gesamte Gruppe.
            # -----------------------------------------------------------------

            team = session.exec(
                select(Team)
                .where(Team.league_group_id == league_group.id)
                .order_by(Team.id)
            ).first()

            if team is None:
                raise RuntimeError(
                    f"LeagueGroup {league_group_id} besitzt kein eigenes Team."
                )

            if team.mytt_team_id is None:
                raise RuntimeError(f"Team {team.id} besitzt keine myTT-Team-ID.")

            if league_group.mytt_slug is None:
                raise RuntimeError(
                    f"LeagueGroup {league_group_id} besitzt keinen myTT-Slug."
                )

            mytt_group_id = league_group.mytt_group_id
            league_slug = league_group.mytt_slug
            mytt_team_id = team.mytt_team_id
            team_name = team.name

            season_string = self._build_mytt_season(
                start_year=season.start_year,
                end_year=season.end_year,
            )

            round_filter = self._get_round_filter(
                season=season,
            )

        # ---------------------------------------------------------------------
        # Tabelle von myTischtennis laden
        # ---------------------------------------------------------------------

        print()
        print("=" * 60)
        print("MYTT LEAGUE TABLE SYNC")
        print("=" * 60)

        print(f"LeagueGroup-ID:     {league_group_id}")
        print(f"myTT Group-ID:      {mytt_group_id}")
        print(f"Saison:             {season_string}")
        print(f"Halbserie:          {round_filter}")
        print(f"API-Team:           {team_name}")
        print(f"myTT Team-ID:       {mytt_team_id}")

        result = await self.client.get_team_player_balances(
            season=season_string,
            league_slug=league_slug,
            group_id=mytt_group_id,
            team_id=mytt_team_id,
            team_name=team_name,
            round_filter=round_filter,
        )

        # ---------------------------------------------------------------------
        # Grundlegende API-Prüfung
        # ---------------------------------------------------------------------

        if not isinstance(result, dict):
            raise RuntimeError(
                f"LeagueGroup {league_group_id}: API-Antwort ist kein Objekt."
            )

        table_data = result.get("tableData")

        if not isinstance(table_data, dict):
            raise RuntimeError(
                f"LeagueGroup {league_group_id}: "
                "'tableData' fehlt oder ist kein Objekt."
            )

        rows = table_data.get("table")

        if not isinstance(rows, list):
            raise RuntimeError(
                f"LeagueGroup {league_group_id}: "
                "'tableData.table' fehlt oder ist keine Liste."
            )

        # ---------------------------------------------------------------------
        # Leere Tabelle
        #
        # Das kann beispielsweise passieren, wenn eine Rückrunde bereits als
        # LeagueGroup existiert, aber bei myTischtennis noch keine Tabelle
        # verfügbar ist.
        #
        # Wichtig:
        # Vorhandene DB-Daten werden in diesem Fall NICHT gelöscht.
        # ---------------------------------------------------------------------

        if not rows:
            print("Keine Tabellendaten vorhanden.")

            return False

        # ---------------------------------------------------------------------
        # Zusätzliche Sicherheitsprüfung
        #
        # Dadurch vermeiden wir, eine versehentlich falsche Gruppe in die DB
        # zu schreiben.
        # ---------------------------------------------------------------------

        response_group_id = self._to_int(result.get("urlid"))

        if response_group_id is not None and response_group_id != mytt_group_id:
            raise RuntimeError(
                f"LeagueGroup {league_group_id}: "
                f"API lieferte Gruppe {response_group_id}, "
                f"erwartet war {mytt_group_id}."
            )

        # ---------------------------------------------------------------------
        # Neue Tabelle zunächst vollständig validieren.
        #
        # Wir tun das VOR dem Löschen der vorhandenen Tabelle.
        # Dadurch bleibt die alte Tabelle erhalten, falls die API plötzlich
        # unvollständige oder unerwartete Daten liefert.
        # ---------------------------------------------------------------------

        parsed_rows = [
            self._parse_table_row(
                row=row,
            )
            for row in rows
        ]

        # ---------------------------------------------------------------------
        # Bestehende Tabelle ersetzen.
        #
        # Alles geschieht in EINER Transaktion:
        #
        # alte Entries löschen
        #          ↓
        # neue Entries anlegen
        #          ↓
        # commit
        #
        # Falls vorher etwas fehlschlägt, bleibt die bisherige Tabelle erhalten.
        # ---------------------------------------------------------------------

        with Session(engine) as session:
            league_group = session.get(
                LeagueGroup,
                league_group_id,
            )

            if league_group is None:
                raise RuntimeError(
                    f"LeagueGroup {league_group_id} "
                    "ist während des Imports verschwunden."
                )

            existing_entries = session.exec(
                select(LeagueTableEntry).where(
                    LeagueTableEntry.league_group_id == league_group_id
                )
            ).all()

            for entry in existing_entries:
                session.delete(entry)

            session.flush()

            for row in parsed_rows:
                entry = LeagueTableEntry(
                    league_group_id=league_group_id,
                    mytt_team_id=row["mytt_team_id"],
                    club_id=row["club_id"],
                    team_name=row["team_name"],
                    position=row["position"],
                    meetings_count=row["meetings_count"],
                    meetings_won=row["meetings_won"],
                    meetings_tie=row["meetings_tie"],
                    meetings_lost=row["meetings_lost"],
                    points_won=row["points_won"],
                    points_lost=row["points_lost"],
                    matches_won=row["matches_won"],
                    matches_lost=row["matches_lost"],
                    sets_won=row["sets_won"],
                    sets_lost=row["sets_lost"],
                    games_won=row["games_won"],
                    games_lost=row["games_lost"],
                )

                session.add(entry)

            session.commit()

        print()
        print("Ligatabelle erfolgreich importiert.")
        print(f"  Tabellenzeilen: {len(parsed_rows)}")

        return True

    # -------------------------------------------------------------------------
    # API-Zeile validieren / normalisieren
    # -------------------------------------------------------------------------

    def _parse_table_row(
        self,
        row: dict,
    ) -> dict:

        if not isinstance(row, dict):
            raise RuntimeError("Tabellenzeile ist kein Objekt.")

        mytt_team_id = self._required_int(
            row,
            "team_id",
        )

        club_id = self._required_str(
            row,
            "club_id",
        )

        team_name = self._required_str(
            row,
            "team_name",
        )

        position = self._required_int(
            row,
            "table_rank",
        )

        return {
            "mytt_team_id": mytt_team_id,
            "club_id": club_id,
            "team_name": team_name,
            "position": position,
            "meetings_count": self._required_int(
                row,
                "meetings_count",
            ),
            "meetings_won": self._required_int(
                row,
                "meetings_won",
            ),
            "meetings_tie": self._required_int(
                row,
                "meetings_tie",
            ),
            "meetings_lost": self._required_int(
                row,
                "meetings_lost",
            ),
            "points_won": self._required_int(
                row,
                "points_won",
            ),
            "points_lost": self._required_int(
                row,
                "points_lost",
            ),
            "matches_won": self._required_int(
                row,
                "matches_won",
            ),
            "matches_lost": self._required_int(
                row,
                "matches_lost",
            ),
            "sets_won": self._required_int(
                row,
                "sets_won",
            ),
            "sets_lost": self._required_int(
                row,
                "sets_lost",
            ),
            "games_won": self._required_int(
                row,
                "games_won",
            ),
            "games_lost": self._required_int(
                row,
                "games_lost",
            ),
        }

    # -------------------------------------------------------------------------
    # VR / RR bestimmen
    # -------------------------------------------------------------------------

    @staticmethod
    def _get_round_filter(
        season: Season,
    ) -> str:

        if season.half == SeasonHalf.VR:
            return "vr"

        if season.half == SeasonHalf.RR:
            return "rr"

        raise RuntimeError(f"Unbekannte Season-Hälfte: {season.half!r}")

    # -------------------------------------------------------------------------
    # myTT-Saisonformat
    #
    # 2018 / 2019 -> "18--19"
    # 2026 / 2027 -> "26--27"
    # -------------------------------------------------------------------------

    @staticmethod
    def _build_mytt_season(
        start_year: int,
        end_year: int,
    ) -> str:

        return f"{start_year % 100:02d}--{end_year % 100:02d}"

    # -------------------------------------------------------------------------
    # Pflichtfelder
    # -------------------------------------------------------------------------

    @classmethod
    def _required_int(
        cls,
        data: dict,
        key: str,
    ) -> int:

        value = cls._to_int(data.get(key))

        if value is None:
            raise RuntimeError(f"Tabellenzeile: Pflichtfeld {key!r} fehlt.")

        return value

    @staticmethod
    def _required_str(
        data: dict,
        key: str,
    ) -> str:

        value = data.get(key)

        if value is None:
            raise RuntimeError(f"Tabellenzeile: Pflichtfeld {key!r} fehlt.")

        result = str(value).strip()

        if not result:
            raise RuntimeError(f"Tabellenzeile: Pflichtfeld {key!r} ist leer.")

        return result

    # -------------------------------------------------------------------------
    # Hilfsfunktion
    # -------------------------------------------------------------------------

    @staticmethod
    def _to_int(
        value,
    ) -> int | None:

        if value is None:
            return None

        return int(value)
