import asyncio
from datetime import datetime, timezone

import httpx
from app.core.database import engine
from app.domains.competition.matches.models import TeamMatch
from app.integrations.mytischtennis.sync.meeting import MeetingSync
from sqlmodel import Session, select

# -------------------------------------------------------------------------
# Einstellungen
# -------------------------------------------------------------------------

# Kleine Pause zwischen erfolgreichen Requests.
# Wir wollen myTischtennis beim historischen Import nicht unnötig belasten.
REQUEST_DELAY_SECONDS = 1.5

# Wie oft ein fehlgeschlagener Request erneut versucht wird.
MAX_RETRIES = 3

# Wartezeit nach dem ersten Fehler.
# Bei jedem weiteren Versuch wird sie verdoppelt:
#
# Versuch 1 -> 5 Sekunden
# Versuch 2 -> 10 Sekunden
# Versuch 3 -> 20 Sekunden
RETRY_DELAY_SECONDS = 5


def get_pending_team_matches() -> list[int]:
    """
    Liefert alle vergangenen TeamMatches, deren Meeting-Details
    noch nicht importiert wurden.

    Der MeetingSync selbst prüft anschließend zusätzlich über die
    myTischtennis-API, ob die Begegnung tatsächlich abgeschlossen ist.
    """

    now = datetime.now(timezone.utc)

    with Session(engine) as session:
        statement = (
            select(TeamMatch)
            .where(
                TeamMatch.mytt_meeting_id.is_not(None),
                TeamMatch.details_imported_at.is_(None),
                TeamMatch.scheduled_at < now,
            )
            .order_by(
                TeamMatch.scheduled_at,
                TeamMatch.id,
            )
        )

        team_matches = session.exec(statement).all()

        return [
            team_match.id for team_match in team_matches if team_match.id is not None
        ]


async def import_team_match(
    sync: MeetingSync,
    team_match_id: int,
) -> tuple[bool, str | None]:
    """
    Importiert ein einzelnes TeamMatch.

    Bei technischen/API-Fehlern wird mehrfach versucht.
    """

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):
        try:
            imported = await sync.sync(
                team_match_id=team_match_id,
            )

            if imported:
                return True, None

            # sync() gibt False zurück, wenn das Meeting z. B.
            # laut API noch nicht abgeschlossen ist.
            return False, "nicht abgeschlossen / übersprungen"

        except (
            httpx.HTTPError,
            RuntimeError,
            ValueError,
        ) as exc:
            print()
            print(f"FEHLER bei TeamMatch {team_match_id}")

            print(f"Versuch {attempt}/{MAX_RETRIES}: {exc}")

            if attempt >= MAX_RETRIES:
                return False, str(exc)

            wait_seconds = RETRY_DELAY_SECONDS * (2 ** (attempt - 1))

            print(f"Nächster Versuch in {wait_seconds} Sekunden ...")

            await asyncio.sleep(wait_seconds)

        except Exception as exc:
            # Unbekannte Fehler wollen wir ebenfalls dokumentieren,
            # aber der gesamte historische Import soll deswegen nicht
            # abbrechen.

            print()
            print(f"UNERWARTETER FEHLER bei TeamMatch {team_match_id}:")

            print(repr(exc))

            return False, repr(exc)

    return False, "unbekannter Fehler"


async def main():

    print()
    print("=" * 70)
    print("MYTT HISTORISCHER MEETING-IMPORT")
    print("=" * 70)

    team_match_ids = get_pending_team_matches()

    total = len(team_match_ids)

    print()
    print(f"Gefundene offene Begegnungen: {total}")

    if total == 0:
        print("Es gibt nichts zu importieren.")

        return

    sync = MeetingSync()

    successful = 0
    skipped = 0

    failed: list[tuple[int, str]] = []

    for index, team_match_id in enumerate(
        team_match_ids,
        start=1,
    ):
        print()
        print("#" * 70)

        print(f"[{index}/{total}] TeamMatch {team_match_id}")

        print("#" * 70)

        imported, error = await import_team_match(
            sync=sync,
            team_match_id=(team_match_id),
        )

        if imported:
            successful += 1

        elif error == "nicht abgeschlossen / übersprungen":
            skipped += 1

        else:
            failed.append(
                (
                    team_match_id,
                    error or "unbekannt",
                )
            )

        # -------------------------------------------------------------
        # Pause zwischen Meetings
        # -------------------------------------------------------------

        if index < total:
            await asyncio.sleep(REQUEST_DELAY_SECONDS)

    # -----------------------------------------------------------------
    # Zusammenfassung
    # -----------------------------------------------------------------

    print()
    print()
    print("=" * 70)
    print("IMPORT ABGESCHLOSSEN")
    print("=" * 70)

    print(f"Gefunden:       {total}")

    print(f"Importiert:     {successful}")

    print(f"Übersprungen:   {skipped}")

    print(f"Fehlgeschlagen: {len(failed)}")

    if failed:
        print()
        print("Fehlgeschlagene TeamMatches:")

        for (
            team_match_id,
            error,
        ) in failed:
            print(f"  {team_match_id}: {error}")


if __name__ == "__main__":
    asyncio.run(main())
