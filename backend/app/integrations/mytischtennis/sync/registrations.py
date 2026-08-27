from app.core.database import engine
from app.core.settings import settings
from app.domains.competition.league.model import LeagueGroup
from app.domains.competition.season.model import Season
from app.domains.competition.teams.model import Team, TeamMembership
from app.domains.members.model import Member, Player
from app.integrations.mytischtennis.api import (
    MyTischtennisClient,
)
from sqlmodel import Session, select


class RegistrationsSync:
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
        # Zuerst nur die Informationen aus der DB laden,
        # die für den API-Request benötigt werden.
        #
        # Dadurch bleibt keine DB-Session während des HTTP-Requests offen.
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

            if not league_group.mytt_slug:
                print(f"LeagueGroup {league_group_id} übersprungen: kein mytt_slug")

                return False

            season_string = self._build_mytt_season_name(
                start_year=season.start_year,
                end_year=season.end_year,
            )

            round_filter = season.half.value

            mytt_group_id = league_group.mytt_group_id
            league_slug = league_group.mytt_slug

            start_year = season.start_year
            end_year = season.end_year
            half = season.half

        # ---------------------------------------------------------------------
        # Ausgabe
        # ---------------------------------------------------------------------

        print()
        print("=" * 60)
        print("MYTT REGISTRATIONS SYNC")
        print("=" * 60)

        print(f"LeagueGroup-ID: {league_group_id}")

        print(f"myTT Group-ID:  {mytt_group_id}")

        print(f"Saison:         {start_year}/{str(end_year)[-2:]} {half.value.upper()}")

        # ---------------------------------------------------------------------
        # Mannschaftsmeldung von myTischtennis laden
        # ---------------------------------------------------------------------

        result = await self.client.get_team_registrations(
            season=season_string,
            league_slug=league_slug,
            group_id=mytt_group_id,
            round_filter=round_filter,
        )

        # ---------------------------------------------------------------------
        # myTT kann trotz HTTP 200 einen Fehler im JSON liefern.
        # ---------------------------------------------------------------------

        api_error = result.get("error")

        if api_error:
            raise RuntimeError(f"myTischtennis meldet einen Fehler: {api_error}")

        data = result.get("data")

        if not isinstance(
            data,
            dict,
        ):
            raise RuntimeError(
                f"LeagueGroup {league_group_id}: 'data' fehlt oder ist kein Objekt."
            )

        teampools = data.get(
            "teampools",
            [],
        )

        if not isinstance(
            teampools,
            list,
        ):
            raise RuntimeError(
                f"LeagueGroup {league_group_id}: 'teampools' ist keine Liste."
            )

        # ---------------------------------------------------------------------
        # Nur unseren Verein verarbeiten
        # ---------------------------------------------------------------------

        own_teampools = [
            teampool
            for teampool in teampools
            if str(teampool.get("clubnr")) == str(settings.mytt_club_number)
        ]

        if not own_teampools:
            print("Kein eigenes Team in dieser Gruppe gefunden.")

            return False

        # ---------------------------------------------------------------------
        # Mannschaftsmeldungen in EINER DB-Transaktion verarbeiten.
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

            season = session.get(
                Season,
                league_group.season_id,
            )

            if season is None:
                raise RuntimeError(
                    f"Season {league_group.season_id} "
                    "ist während des Imports verschwunden."
                )

            teams_updated = 0

            players_created = 0
            players_updated = 0

            memberships_created = 0
            memberships_updated = 0
            memberships_deleted = 0

            group_was_processed = False

            # -----------------------------------------------------------------
            # Eine Gruppe kann mehrere eigene Mannschaften enthalten.
            # -----------------------------------------------------------------

            for teampool in own_teampools:
                result_stats = self._sync_teampool(
                    session=session,
                    season=season,
                    league_group=league_group,
                    teampool=teampool,
                )

                if result_stats is None:
                    continue

                group_was_processed = True

                teams_updated += 1

                players_created += result_stats["players_created"]

                players_updated += result_stats["players_updated"]

                memberships_created += result_stats["memberships_created"]

                memberships_updated += result_stats["memberships_updated"]

                memberships_deleted += result_stats["memberships_deleted"]

            if not group_was_processed:
                print("Keine Mannschaftsmeldung konnte verarbeitet werden.")

                return False

            session.commit()

        # ---------------------------------------------------------------------
        # Zusammenfassung
        # ---------------------------------------------------------------------

        print()
        print("Mannschaftsmeldung erfolgreich importiert:")

        print(f"  Teams aktualisiert:       {teams_updated}")

        print(f"  Spieler neu:              {players_created}")

        print(f"  Spieler aktualisiert:     {players_updated}")

        print(f"  Memberships neu:          {memberships_created}")

        print(f"  Memberships aktualisiert: {memberships_updated}")

        print(f"  Memberships entfernt:     {memberships_deleted}")

        return True

    # -------------------------------------------------------------------------
    # Mannschaftsmeldung eines eigenen Teams verarbeiten
    # -------------------------------------------------------------------------

    def _sync_teampool(
        self,
        session: Session,
        season: Season,
        league_group: LeagueGroup,
        teampool: dict,
    ) -> dict | None:

        team_name = (teampool.get("team_name") or "").strip()

        players_data = teampool.get(
            "teampool",
            [],
        )

        # ---------------------------------------------------------------------
        # Historische Sonderfälle:
        #
        # Teilweise existiert eine Mannschaftsmeldung, aber myTT liefert
        # teampool=None. Diese Fälle sind bekannt und werden bewusst
        # übersprungen.
        # ---------------------------------------------------------------------

        if not isinstance(
            players_data,
            list,
        ):
            print(f"  Team {team_name} übersprungen: teampool ist keine Liste")

            return None

        # ---------------------------------------------------------------------
        # Mannschaftsnummer bestimmen
        # ---------------------------------------------------------------------

        team_number = self._get_team_number(players_data)

        # ---------------------------------------------------------------------
        # Passendes Team in unserer DB finden
        # ---------------------------------------------------------------------

        team = self._find_team(
            session=session,
            season=season,
            league_group=league_group,
            team_name=team_name,
            team_number=team_number,
        )

        if team is None:
            print(f"  Team nicht eindeutig gefunden: {team_name}")

            return None

        # ---------------------------------------------------------------------
        # Team aktualisieren
        # ---------------------------------------------------------------------

        if team_number is not None:
            team.team_number = team_number

        if team_name:
            team.name = team_name

        print(f"  Team: {team.name} (Nr. {team.team_number})")

        # ---------------------------------------------------------------------
        # Spieler / Memberships
        # ---------------------------------------------------------------------

        players_created = 0
        players_updated = 0

        memberships_created = 0
        memberships_updated = 0

        seen_player_ids: set[int] = set()

        for player_data in players_data:
            player, player_created = self._sync_player(
                session=session,
                player_data=player_data,
            )

            if player is None:
                continue

            if player_created:
                players_created += 1

            else:
                players_updated += 1

            session.flush()

            if player.id is None:
                raise RuntimeError("Player besitzt nach flush() keine ID.")

            seen_player_ids.add(player.id)

            membership_created = self._sync_membership(
                session=session,
                team=team,
                player=player,
                player_data=player_data,
            )

            if membership_created:
                memberships_created += 1

            else:
                memberships_updated += 1

        # ---------------------------------------------------------------------
        # Alte Memberships entfernen
        #
        # Die Mannschaftsmeldung ist für diese Halbserie die maßgebliche
        # Quelle.
        # ---------------------------------------------------------------------

        existing_memberships = session.exec(
            select(TeamMembership).where(TeamMembership.team_id == team.id)
        ).all()

        memberships_deleted = 0

        for membership in existing_memberships:
            if membership.player_id not in seen_player_ids:
                session.delete(membership)

                memberships_deleted += 1

        return {
            "players_created": players_created,
            "players_updated": players_updated,
            "memberships_created": memberships_created,
            "memberships_updated": memberships_updated,
            "memberships_deleted": memberships_deleted,
        }

    # -------------------------------------------------------------------------
    # Team finden
    # -------------------------------------------------------------------------

    def _find_team(
        self,
        session: Session,
        season: Season,
        league_group: LeagueGroup,
        team_name: str,
        team_number: int | None,
    ) -> Team | None:

        teams = session.exec(
            select(Team).where(
                Team.season_id == season.id,
                Team.league_group_id == league_group.id,
            )
        ).all()

        if not teams:
            return None

        # ---------------------------------------------------------------------
        # Nur ein eigenes Team in der Gruppe
        # ---------------------------------------------------------------------

        if len(teams) == 1:
            return teams[0]

        # ---------------------------------------------------------------------
        # Mannschaftsnummer
        # ---------------------------------------------------------------------

        if team_number is not None:
            number_matches = [team for team in teams if team.team_number == team_number]

            if len(number_matches) == 1:
                return number_matches[0]

        # ---------------------------------------------------------------------
        # Fallback über Mannschaftsname
        # ---------------------------------------------------------------------

        normalized_name = self._normalize_name(team_name)

        name_matches = [
            team for team in teams if self._normalize_name(team.name) == normalized_name
        ]

        if len(name_matches) == 1:
            return name_matches[0]

        return None

    # -------------------------------------------------------------------------
    # Spieler
    # -------------------------------------------------------------------------

    def _sync_player(
        self,
        session: Session,
        player_data: dict,
    ) -> tuple[Player | None, bool]:

        # ---------------------------------------------------------------------
        # player_id aus der Mannschaftsmeldung ist die NUID.
        #
        # Beispiel:
        # NU70645
        # ---------------------------------------------------------------------

        nuid = (player_data.get("player_id") or "").strip()

        if not nuid:
            print("    Spieler ohne NUID übersprungen")

            return None, False

        first_name = (player_data.get("player_firstname") or "").strip()

        last_name = (player_data.get("player_lastname") or "").strip()

        player = session.exec(select(Player).where(Player.nuid == nuid)).first()

        # ---------------------------------------------------------------------
        # Bereits vorhanden
        # ---------------------------------------------------------------------

        if player is not None:
            member = session.get(
                Member,
                player.member_id,
            )

            if member is None:
                raise RuntimeError(
                    f"Player {player.id} verweist auf "
                    f"Member {player.member_id}, "
                    "der nicht existiert."
                )

            if first_name:
                member.first_name = first_name

            if last_name:
                member.last_name = last_name

            return player, False

        # ---------------------------------------------------------------------
        # Neuer Member
        # ---------------------------------------------------------------------

        member = Member(
            first_name=first_name,
            last_name=last_name,
        )

        session.add(member)

        session.flush()

        if member.id is None:
            raise RuntimeError("Member besitzt nach flush() keine ID.")

        # ---------------------------------------------------------------------
        # Neuer Player
        # ---------------------------------------------------------------------

        player = Player(
            member_id=member.id,
            nuid=nuid,
            mytt_person_id=None,
        )

        session.add(player)

        session.flush()

        if player.id is None:
            raise RuntimeError("Player besitzt nach flush() keine ID.")

        print(f"    NEU: {first_name} {last_name} ({nuid})")

        return player, True

    # -------------------------------------------------------------------------
    # TeamMembership
    # -------------------------------------------------------------------------

    def _sync_membership(
        self,
        session: Session,
        team: Team,
        player: Player,
        player_data: dict,
    ) -> bool:

        membership = session.exec(
            select(TeamMembership).where(
                TeamMembership.team_id == team.id,
                TeamMembership.player_id == player.id,
            )
        ).first()

        player_rank = player_data.get("player_rank")

        rank = str(player_rank) if player_rank is not None else None

        status = player_data.get("player_status")

        # ---------------------------------------------------------------------
        # Vorhanden
        # ---------------------------------------------------------------------

        if membership is not None:
            membership.rank = rank
            membership.status = status

            return False

        # ---------------------------------------------------------------------
        # Neu
        # ---------------------------------------------------------------------

        if team.id is None:
            raise RuntimeError("Team besitzt keine ID.")

        if player.id is None:
            raise RuntimeError("Player besitzt keine ID.")

        membership = TeamMembership(
            team_id=team.id,
            player_id=player.id,
            rank=rank,
            status=status,
        )

        session.add(membership)

        return True

    # -------------------------------------------------------------------------
    # Teamnummer aus Spielern bestimmen
    # -------------------------------------------------------------------------

    @staticmethod
    def _get_team_number(
        players_data: list[dict],
    ) -> int | None:

        team_numbers = {
            int(player["team_number"])
            for player in players_data
            if player.get("team_number") is not None
        }

        if not team_numbers:
            return None

        if len(team_numbers) > 1:
            raise ValueError(
                f"Mannschaftsmeldung enthält mehrere team_number-Werte: {team_numbers}"
            )

        return next(iter(team_numbers))

    # -------------------------------------------------------------------------
    # myTT-Saisonformat
    #
    # 2018 / 2019 -> "18--19"
    # -------------------------------------------------------------------------

    @staticmethod
    def _build_mytt_season_name(
        start_year: int,
        end_year: int,
    ) -> str:

        return f"{start_year % 100:02d}--{end_year % 100:02d}"

    # -------------------------------------------------------------------------
    # Namen vergleichbar machen
    # -------------------------------------------------------------------------

    @staticmethod
    def _normalize_name(
        value: str,
    ) -> str:

        return " ".join(value.split()).casefold()


# ---------------------------------------------------------------------------
# Bekannte Besonderheiten historischer Mannschaftsmeldungen
# ---------------------------------------------------------------------------
#
# Einige historische Mannschaftsmeldungen sind auf myTischtennis nicht
# vollständig bzw. nicht eindeutig.
#
# Bekannte Fälle mit teampool=None:
#
# 2008/09 VR
#   Gruppe 84748
#   TTC Langen-Brombach IV
#
# 2009/10 RR
#   Gruppe 126473
#   TTC Langen-Brombach II
#
# 2010/11 VR
#   Gruppe 140199
#   TTC Langen-Brombach III
#
# Außerdem existiert 2011/12 RR ein mehrdeutiger Sonderfall bei Team 939856.
# Diese Fälle werden bewusst nicht künstlich rekonstruiert.
#
# ---------------------------------------------------------------------------
