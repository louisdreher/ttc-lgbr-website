import logging
from datetime import datetime, timezone

from app.core.database import engine
from app.domains.competition.matches.models import (
    GameType,
    Match,
    MatchLineup,
    MatchParticipant,
    SetResult,
    TeamMatch,
)
from app.domains.members.model import Member, Player
from app.integrations.mytischtennis.api import (
    MyTischtennisClient,
)
from sqlmodel import Session, select


logger = logging.getLogger(__name__)


class MeetingSync:
    def __init__(self):
        self.client = MyTischtennisClient()

    # -------------------------------------------------------------------------
    # Öffentlicher Einstieg über TeamMatch-ID
    # -------------------------------------------------------------------------

    async def sync(
        self,
        team_match_id: int,
        force: bool = False,
    ) -> bool:

        # ---------------------------------------------------------------------
        # Zuerst nur die benötigten Daten aus der DB laden.
        #
        # Die DB-Session bleibt dadurch nicht während des HTTP-Requests offen.
        # ---------------------------------------------------------------------

        with Session(engine) as session:
            team_match = session.get(
                TeamMatch,
                team_match_id,
            )

            if team_match is None:
                raise ValueError(f"TeamMatch {team_match_id} existiert nicht.")

            if team_match.mytt_meeting_id is None:
                raise ValueError(
                    f"TeamMatch {team_match_id} hat keine myTT meeting_id."
                )

            if team_match.details_imported_at is not None and not force:
                logger.info(
                    "Meeting-Sync übersprungen: "
                    "team_match_id=%s reason=details_already_imported",
                    team_match_id,
                )

                return False

            meeting_id = team_match.mytt_meeting_id

        # ---------------------------------------------------------------------
        # Meeting von myTischtennis laden
        # ---------------------------------------------------------------------

        logger.info(
            "Meeting-Sync gestartet: team_match_id=%s mytt_meeting_id=%s force=%s",
            team_match_id,
            meeting_id,
            force,
        )

        result = await self.client.get_meeting(
            meeting_id=meeting_id,
        )

        api_error = result.get("error")

        if api_error:
            raise RuntimeError(f"myTischtennis meldet einen Fehler: {api_error}")

        data = result.get("data")

        if not isinstance(
            data,
            dict,
        ):
            raise RuntimeError(
                f"Meeting {meeting_id}: 'data' fehlt oder ist kein Objekt."
            )

        # ---------------------------------------------------------------------
        # Nur abgeschlossene Begegnungen vollständig importieren
        # ---------------------------------------------------------------------

        is_completed = (
            data.get("is_completed") is True or data.get("is_meeting_complete") is True
        )

        if not is_completed:
            logger.info(
                "Meeting-Sync übersprungen: "
                "team_match_id=%s mytt_meeting_id=%s reason=not_completed",
                team_match_id,
                meeting_id,
            )

            return False

        matches_data = data.get("match")

        if not isinstance(
            matches_data,
            list,
        ):
            raise RuntimeError(f"Meeting {meeting_id}: 'match' ist keine Liste.")

        # ---------------------------------------------------------------------
        # Alles in EINER DB-Transaktion speichern.
        #
        # Erst der commit() ganz am Ende schreibt dauerhaft.
        # Schlägt vorher etwas fehl, bleibt details_imported_at leer.
        # ---------------------------------------------------------------------

        with Session(engine) as session:
            team_match = session.get(
                TeamMatch,
                team_match_id,
            )

            if team_match is None:
                raise RuntimeError(
                    f"TeamMatch {team_match_id} ist während des Imports verschwunden."
                )

            # -----------------------------------------------------------------
            # Falls force=True oder ein früherer Test bereits Detaildaten
            # erzeugt hat: vorhandene Details entfernen.
            #
            # Dadurch ist der Import sauber wiederholbar.
            # -----------------------------------------------------------------

            self._clear_existing_details(
                session=session,
                team_match=team_match,
            )

            # -----------------------------------------------------------------
            # TeamMatch mit genaueren Meeting-Daten anreichern
            # -----------------------------------------------------------------

            self._update_team_match(
                team_match=team_match,
                data=data,
                is_completed=is_completed,
            )

            # -----------------------------------------------------------------
            # Aufstellung aus ALLEN API-Matches auslesen.
            #
            # Bewusst auch aus theoretisch nicht mehr ausgespielten Matches:
            # diese enthalten bei alten Spielsystemen trotzdem Informationen
            # darüber, welche Spieler aufgestellt waren.
            # -----------------------------------------------------------------

            lineup_count = self._sync_lineup(
                session=session,
                team_match=team_match,
                matches_data=matches_data,
            )

            # -----------------------------------------------------------------
            # Tatsächlich gespielte Matches importieren
            # -----------------------------------------------------------------

            imported_matches = 0
            skipped_matches = 0
            participant_count = 0
            set_count = 0

            for sequence, match_data in enumerate(
                matches_data,
                start=1,
            ):
                if not self._is_played_match(match_data):
                    skipped_matches += 1

                    continue

                match = self._create_match(
                    session=session,
                    team_match=team_match,
                    match_data=match_data,
                    sequence=sequence,
                )

                imported_matches += 1

                participant_count += self._create_participants(
                    session=session,
                    team_match=team_match,
                    match=match,
                    match_data=match_data,
                )

                set_count += self._create_set_results(
                    session=session,
                    team_match=team_match,
                    match=match,
                    match_data=match_data,
                )

            # -----------------------------------------------------------------
            # Erst JETZT gilt das Meeting als vollständig importiert.
            # -----------------------------------------------------------------

            team_match.details_imported_at = datetime.now(timezone.utc)

            session.add(team_match)

            session.commit()

        # ---------------------------------------------------------------------
        # Zusammenfassung
        # ---------------------------------------------------------------------

        logger.info(
            "Meeting-Sync abgeschlossen: team_match_id=%s mytt_meeting_id=%s "
            "lineup_players=%s matches=%s skipped_matches=%s "
            "participants=%s sets=%s",
            team_match_id,
            meeting_id,
            lineup_count,
            imported_matches,
            skipped_matches,
            participant_count,
            set_count,
        )

        return True

    # -------------------------------------------------------------------------
    # Alternativer Einstieg über myTT meeting_id
    # -------------------------------------------------------------------------

    async def sync_by_meeting_id(
        self,
        meeting_id: int,
        force: bool = False,
    ) -> bool:

        with Session(engine) as session:
            team_match = session.exec(
                select(TeamMatch).where(TeamMatch.mytt_meeting_id == meeting_id)
            ).first()

            if team_match is None:
                raise ValueError(
                    f"Kein TeamMatch mit myTT meeting_id {meeting_id} gefunden."
                )

            team_match_id = team_match.id

        if team_match_id is None:
            raise RuntimeError("TeamMatch besitzt keine ID.")

        return await self.sync(
            team_match_id=team_match_id,
            force=force,
        )

    # -------------------------------------------------------------------------
    # Vorhandene Detaildaten löschen
    # -------------------------------------------------------------------------

    def _clear_existing_details(
        self,
        session: Session,
        team_match: TeamMatch,
    ) -> None:

        if team_match.id is None:
            raise RuntimeError("TeamMatch besitzt keine ID.")

        matches = session.exec(
            select(Match).where(Match.team_match_id == team_match.id)
        ).all()

        for match in matches:
            if match.id is None:
                continue

            participants = session.exec(
                select(MatchParticipant).where(MatchParticipant.match_id == match.id)
            ).all()

            for participant in participants:
                session.delete(participant)

            set_results = session.exec(
                select(SetResult).where(SetResult.match_id == match.id)
            ).all()

            for set_result in set_results:
                session.delete(set_result)

            session.delete(match)

        lineups = session.exec(
            select(MatchLineup).where(MatchLineup.team_match_id == team_match.id)
        ).all()

        for lineup in lineups:
            session.delete(lineup)

        session.flush()

    # -------------------------------------------------------------------------
    # TeamMatch aktualisieren
    # -------------------------------------------------------------------------


def _update_team_match(
    self,
    team_match: TeamMatch,
    data: dict,
    is_completed: bool,
) -> None:

    team_match.is_completed = is_completed

    started_at = self._parse_datetime(data.get("start_date"))

    ended_at = self._parse_datetime(data.get("end_date"))

    if started_at is not None:
        team_match.started_at = started_at

    if ended_at is not None:
        team_match.ended_at = ended_at

    play_mode = data.get("play_mode")

    if play_mode:
        team_match.play_mode = str(play_mode)

        # usw...

        # ---------------------------------------------------------------------
        # Halle
        # ---------------------------------------------------------------------

        location = data.get("location")

        if isinstance(
            location,
            dict,
        ):
            venue_name = location.get("label") or data.get("court_hall_name")

            if venue_name:
                team_match.venue_name = str(venue_name)

            venue_street = location.get("street")

            if venue_street:
                team_match.venue_street = str(venue_street)

            venue_city = location.get("city")

            if venue_city:
                team_match.venue_city = str(venue_city)

        # ---------------------------------------------------------------------
        # Mannschaftsergebnis auf TTC-Sicht drehen
        # ---------------------------------------------------------------------

        matches_home = self._to_int(data.get("matches_home"))

        matches_guest = self._to_int(data.get("matches_guest"))

        if matches_home is not None and matches_guest is not None:
            if team_match.is_home:
                team_match.score_ttc = matches_home

                team_match.score_opponent = matches_guest

            else:
                team_match.score_ttc = matches_guest

                team_match.score_opponent = matches_home

    # -------------------------------------------------------------------------
    # Aufstellung
    # -------------------------------------------------------------------------

    def _sync_lineup(
        self,
        session: Session,
        team_match: TeamMatch,
        matches_data: list[dict],
    ) -> int:

        if team_match.id is None:
            raise RuntimeError("TeamMatch besitzt keine ID.")

        lineups_by_player: dict[
            int,
            MatchLineup,
        ] = {}

        for match_data in matches_data:
            game_type = self._parse_game_type(match_data)

            ttc_players = self._get_ttc_player_data(
                team_match=team_match,
                match_data=match_data,
            )

            for player_data in ttc_players:
                # "Nicht anwesend" ist kein echter Spieler
                # und gehört deshalb nicht in die Aufstellung.
                if str(player_data.get("person_id") or "").strip() == "NU74837":
                    continue

                player = self._get_or_create_player(
                    session=session,
                    player_data=player_data,
                )

                if player.id is None:
                    raise RuntimeError("Player besitzt nach flush() keine ID.")

                lineup = lineups_by_player.get(player.id)

                if lineup is None:
                    lineup = MatchLineup(
                        team_match_id=(team_match.id),
                        player_id=player.id,
                    )

                    lineups_by_player[player.id] = lineup

                player_rank = self._to_int(player_data.get("player_rank"))

                # -------------------------------------------------------------
                # Beim Einzel beschreibt player_rank die Position.
                # Beim Doppel entspricht er im beobachteten API-Format
                # der Doppelnummer.
                # -------------------------------------------------------------

                if game_type == GameType.SINGLE and player_rank is not None:
                    lineup.position = player_rank

                elif game_type == GameType.DOUBLE and player_rank is not None:
                    lineup.doubles_pair = player_rank

        for lineup in lineups_by_player.values():
            session.add(lineup)

        session.flush()

        return len(lineups_by_player)

    # -------------------------------------------------------------------------
    # Match
    # -------------------------------------------------------------------------

    def _create_match(
        self,
        session: Session,
        team_match: TeamMatch,
        match_data: dict,
        sequence: int,
    ) -> Match:

        if team_match.id is None:
            raise RuntimeError("TeamMatch besitzt keine ID.")

        game_type = self._parse_game_type(match_data)

        match_uuid = match_data.get("match_uuid")

        match_name = match_data.get("match_name")

        match = Match(
            team_match_id=team_match.id,
            sequence=sequence,
            game_type=game_type,
            mytt_match_uuid=(str(match_uuid) if match_uuid else None),
            match_name=(str(match_name) if match_name else None),
        )

        session.add(match)

        # Wir brauchen match.id bereits für
        # Teilnehmer und Satzergebnisse.
        session.flush()

        if match.id is None:
            raise RuntimeError("Match besitzt nach flush() keine ID.")

        return match

    # -------------------------------------------------------------------------
    # MatchParticipant
    # -------------------------------------------------------------------------

    def _create_participants(
        self,
        session: Session,
        team_match: TeamMatch,
        match: Match,
        match_data: dict,
    ) -> int:

        if match.id is None:
            raise RuntimeError("Match besitzt keine ID.")

        ttc_players = self._get_ttc_player_data(
            team_match=team_match,
            match_data=match_data,
        )

        opponent_players = self._get_opponent_player_data(
            team_match=team_match,
            match_data=match_data,
        )

        opponent_name = self._build_opponent_name(opponent_players)

        count = 0
        seen_player_ids: set[int] = set()

        for player_data in ttc_players:
            player = self._get_or_create_player(
                session=session,
                player_data=player_data,
            )

            if player.id is None:
                raise RuntimeError("Player besitzt keine ID.")

            if player.id in seen_player_ids:
                continue

            seen_player_ids.add(player.id)

            participant = MatchParticipant(
                match_id=match.id,
                player_id=player.id,
                opponent_name=(opponent_name),
            )

            session.add(participant)

            count += 1

        session.flush()

        return count

    # -------------------------------------------------------------------------
    # Satzergebnisse
    # -------------------------------------------------------------------------

    def _create_set_results(
        self,
        session: Session,
        team_match: TeamMatch,
        match: Match,
        match_data: dict,
    ) -> int:

        if match.id is None:
            raise RuntimeError("Match besitzt keine ID.")

        count = 0

        for set_number in range(
            1,
            6,
        ):
            home_points = self._to_int(match_data.get(f"set{set_number}_home"))

            guest_points = self._to_int(match_data.get(f"set{set_number}_guest"))

            # -------------------------------------------------------------
            # Satz nicht vorhanden
            # -------------------------------------------------------------

            if home_points is None or guest_points is None:
                continue

            # -------------------------------------------------------------
            # 0:0 bedeutet im myTT-Datensatz:
            # dieser Satz wurde nicht gespielt.
            #
            # Ein echtes 0:11 bleibt erhalten, da nur beide 0 sein müssen.
            # -------------------------------------------------------------

            if home_points == 0 and guest_points == 0:
                continue

            if team_match.is_home:
                points_ttc = home_points

                points_opponent = guest_points

            else:
                points_ttc = guest_points

                points_opponent = home_points

            set_result = SetResult(
                match_id=match.id,
                set_number=set_number,
                points_ttc=points_ttc,
                points_opponent=(points_opponent),
            )

            session.add(set_result)

            count += 1

        session.flush()

        return count

    # -------------------------------------------------------------------------
    # TTC-Spieler bestimmen
    # -------------------------------------------------------------------------

    @staticmethod
    def _get_ttc_player_data(
        team_match: TeamMatch,
        match_data: dict,
    ) -> list[dict]:

        if team_match.is_home:
            keys = (
                "mm_player11",
                "mm_player12",
            )

        else:
            keys = (
                "mm_player21",
                "mm_player22",
            )

        return [
            player_data
            for key in keys
            if isinstance(
                (player_data := match_data.get(key)),
                dict,
            )
        ]

    # -------------------------------------------------------------------------
    # Gegner bestimmen
    # -------------------------------------------------------------------------

    @staticmethod
    def _get_opponent_player_data(
        team_match: TeamMatch,
        match_data: dict,
    ) -> list[dict]:

        if team_match.is_home:
            keys = (
                "mm_player21",
                "mm_player22",
            )

        else:
            keys = (
                "mm_player11",
                "mm_player12",
            )

        return [
            player_data
            for key in keys
            if isinstance(
                (player_data := match_data.get(key)),
                dict,
            )
        ]

    # -------------------------------------------------------------------------
    # Gegnername
    # -------------------------------------------------------------------------

    @staticmethod
    def _build_opponent_name(
        players: list[dict],
    ) -> str | None:

        names = []

        for player in players:
            nuid = str(player.get("person_id") or "").strip()

            if nuid == "NU74837":
                names.append("Nicht anwesend")
                continue

            first_name = str(player.get("firstname") or "").strip()

            last_name = str(player.get("lastname") or "").strip()

            full_name = (f"{first_name} {last_name}").strip()

            if full_name:
                names.append(full_name)

        if not names:
            return None

        return " / ".join(names)

    # -------------------------------------------------------------------------
    # Player suchen / anlegen
    # -------------------------------------------------------------------------

    def _get_or_create_player(
        self,
        session: Session,
        player_data: dict,
    ) -> Player:

        # ---------------------------------------------------------------------
        # WICHTIG:
        #
        # person_id = NUID, z.B. "NU70645"
        # player_id = numerische myTT-Spieler-ID, z.B. "232268"
        #
        # Niemals anhand des Namens identifizieren.
        # ---------------------------------------------------------------------

        nuid_raw = player_data.get("person_id")

        mytt_player_id_raw = player_data.get("player_id")

        nuid = str(nuid_raw).strip() if nuid_raw else None

        mytt_player_id = str(mytt_player_id_raw).strip() if mytt_player_id_raw else None

        if nuid is None and mytt_player_id is None:
            raise RuntimeError("Spieler besitzt weder NUID noch myTT player_id.")

        # ---------------------------------------------------------------------
        # Beide IDs separat prüfen.
        # ---------------------------------------------------------------------

        player_by_nuid = None
        player_by_mytt_id = None

        if nuid is not None:
            player_by_nuid = session.exec(
                select(Player).where(Player.nuid == nuid)
            ).first()

        if mytt_player_id is not None:
            player_by_mytt_id = session.exec(
                select(Player).where(Player.mytt_person_id == mytt_player_id)
            ).first()

        # ---------------------------------------------------------------------
        # Nicht Anwesende Player abfangen
        # ---------------------------------------------------------------------

        if nuid == "NU74837":
            player = session.exec(
                select(Player).where(Player.nuid == "NU74837")
            ).first()

            if player is not None:
                return player

            member = Member(
                first_name="Nicht",
                last_name="anwesend",
                is_active=False,
            )

            session.add(member)
            session.flush()

            player = Player(
                member_id=member.id,
                nuid="NU74837",
                mytt_person_id=mytt_player_id,
            )

            session.add(player)
            session.flush()

            return player

        # ---------------------------------------------------------------------
        # Sicherheitsprüfung:
        # NUID und myTT-ID dürfen nicht auf zwei unterschiedliche Player zeigen.
        # ---------------------------------------------------------------------

        if (
            player_by_nuid is not None
            and player_by_mytt_id is not None
            and player_by_nuid.id != player_by_mytt_id.id
        ):
            raise RuntimeError(
                f"Spieler-ID-Konflikt: "
                f"NUID {nuid} und "
                f"myTT player_id "
                f"{mytt_player_id} "
                f"zeigen auf verschiedene "
                f"Player."
            )

        player = player_by_nuid or player_by_mytt_id

        # ---------------------------------------------------------------------
        # Bereits vorhanden
        # ---------------------------------------------------------------------

        if player is not None:
            if player.nuid is None and nuid is not None:
                player.nuid = nuid

            if player.mytt_person_id is None and mytt_player_id is not None:
                player.mytt_person_id = mytt_player_id

            session.add(player)

            session.flush()

            return player

        # ---------------------------------------------------------------------
        # Neuer Spieler
        # ---------------------------------------------------------------------

        first_name = str(player_data.get("firstname") or "").strip()

        last_name = str(player_data.get("lastname") or "").strip()

        if not first_name or not last_name:
            raise RuntimeError(
                f"Neuer Spieler {nuid or mytt_player_id}: Vor- oder Nachname fehlt."
            )

        member = Member(
            first_name=first_name,
            last_name=last_name,
        )

        session.add(member)

        session.flush()

        if member.id is None:
            raise RuntimeError("Member besitzt nach flush() keine ID.")

        player = Player(
            member_id=member.id,
            nuid=nuid,
            mytt_person_id=(mytt_player_id),
        )

        session.add(player)

        session.flush()

        if player.id is None:
            raise RuntimeError("Player besitzt nach flush() keine ID.")

        logger.debug(
            "Player aus Meeting angelegt: player_id=%s nuid=%s",
            player.id,
            nuid,
        )

        return player

    # -------------------------------------------------------------------------
    # Wurde das Match tatsächlich gespielt?
    # -------------------------------------------------------------------------

    @classmethod
    def _is_played_match(
        cls,
        match_data: dict,
    ) -> bool:

        matches_home = cls._to_int(match_data.get("matches_home")) or 0

        matches_guest = cls._to_int(match_data.get("matches_guest")) or 0

        if matches_home > 0 or matches_guest > 0:
            return True

        # ---------------------------------------------------------------------
        # Kampflos / Strafwertung zählt ebenfalls als Match,
        # auch wenn keine Satzergebnisse vorhanden sind.
        # ---------------------------------------------------------------------

        if bool(match_data.get("home_wo")):
            return True

        if bool(match_data.get("guest_wo")):
            return True

        if bool(match_data.get("home_penalty")):
            return True

        if bool(match_data.get("guest_penalty")):
            return True

        return False

    # -------------------------------------------------------------------------
    # GameType
    # -------------------------------------------------------------------------

    @staticmethod
    def _parse_game_type(
        match_data: dict,
    ) -> GameType:

        value = match_data.get("game_type")

        try:
            return GameType(value)

        except ValueError as exc:
            raise RuntimeError(f"Unbekannter game_type: {value!r}") from exc

    # -------------------------------------------------------------------------
    # Hilfsfunktionen
    # -------------------------------------------------------------------------

    @staticmethod
    def _to_int(
        value,
    ) -> int | None:

        if value is None:
            return None

        return int(value)

    @staticmethod
    def _parse_datetime(
        value,
    ) -> datetime | None:

        if not value:
            return None

        return datetime.fromisoformat(str(value))
