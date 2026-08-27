import asyncio
import json

import httpx
from app.core.database import engine
from app.domains.competition.league.model import (
    LeagueGroup,
    LeagueTableEntry,
)
from app.domains.competition.teams.model import Team
from app.integrations.mytischtennis.sync.league_table import (
    LeagueTableSync,
)
from sqlmodel import Session, select

# ---------------------------------------------------------------------------
# KONFIGURATION
# ---------------------------------------------------------------------------

# Kleine Pause zwischen den Requests, damit wir myTischtennis
# nicht unnötig schnell hintereinander abfragen.
REQUEST_DELAY = 1.5

# Anzahl der Versuche bei temporären Fehlern.
MAX_RETRIES = 3

# Wartezeit:
# Versuch 1 fehlgeschlagen -> 5 Sekunden
# Versuch 2 fehlgeschlagen -> 10 Sekunden
RETRY_BASE_DELAY = 5.0

# Für den historischen Erstimport sinnvoll:
#
# True:
#   LeagueGroups, für die bereits Tabellenzeilen vorhanden sind,
#   werden übersprungen.
#
# False:
#   Auch vorhandene Tabellen werden erneut über die API geladen
#   und durch LeagueTableSync ersetzt.
SKIP_EXISTING = True


# ---------------------------------------------------------------------------
# HILFSFUNKTION
# ---------------------------------------------------------------------------


def has_existing_table(
    league_group_id: int,
) -> bool:

    with Session(engine) as session:
        existing_entry = session.exec(
            select(LeagueTableEntry.id)
            .where(LeagueTableEntry.league_group_id == league_group_id)
            .limit(1)
        ).first()

        return existing_entry is not None


# ---------------------------------------------------------------------------
# EINZELNE LEAGUEGROUP IMPORTIEREN
# ---------------------------------------------------------------------------


async def import_league_group(
    sync: LeagueTableSync,
    league_group_id: int,
) -> str:

    # -----------------------------------------------------------------------
    # Bereits vorhanden
    # -----------------------------------------------------------------------

    if SKIP_EXISTING and has_existing_table(league_group_id):
        print(f"LeagueGroup {league_group_id}: Tabelle bereits vorhanden.")

        return "skipped"

    # -----------------------------------------------------------------------
    # Import mit Retry
    # -----------------------------------------------------------------------

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):
        try:
            imported = await sync.sync(
                league_group_id=league_group_id,
            )

            if imported:
                return "imported"

            # sync() gibt False zurück, wenn z.B. noch keine
            # Tabellendaten vorhanden sind.
            return "skipped"

        except (
            httpx.HTTPError,
            json.JSONDecodeError,
        ) as exc:
            print()
            print(
                f"LeagueGroup {league_group_id}: "
                f"temporärer Fehler "
                f"(Versuch {attempt}/{MAX_RETRIES})"
            )

            print(f"  {type(exc).__name__}: {exc}")

            if attempt >= MAX_RETRIES:
                return "failed"

            wait_seconds = RETRY_BASE_DELAY * attempt

            print(f"  Neuer Versuch in {wait_seconds:.0f} Sekunden ...")

            await asyncio.sleep(wait_seconds)

        except Exception as exc:
            # ---------------------------------------------------------------
            # Andere Fehler sind eher Daten-/Programmierfehler.
            # Diese nicht mehrfach gegen die API schicken.
            # ---------------------------------------------------------------

            print()
            print(f"LeagueGroup {league_group_id}: FEHLER")

            print(f"  {type(exc).__name__}: {exc}")

            return "failed"

    return "failed"


# ---------------------------------------------------------------------------
# HAUPTPROGRAMM
# ---------------------------------------------------------------------------


async def main():

    print()
    print("=" * 70)
    print("HISTORISCHER MYTT LIGATABELLEN-IMPORT")
    print("=" * 70)

    # -----------------------------------------------------------------------
    # Alle LeagueGroups bestimmen, zu denen mindestens ein eigenes Team
    # existiert.
    #
    # DISTINCT ist wichtig:
    # Mehrere TTC-Teams könnten theoretisch derselben LeagueGroup
    # zugeordnet sein. Die Tabelle soll trotzdem nur einmal geladen werden.
    # -----------------------------------------------------------------------

    with Session(engine) as session:
        league_groups = session.exec(
            select(LeagueGroup)
            .join(
                Team,
                Team.league_group_id == LeagueGroup.id,
            )
            .distinct()
            .order_by(LeagueGroup.id)
        ).all()

        league_group_ids = [
            league_group.id
            for league_group in league_groups
            if league_group.id is not None
        ]

    print()
    print(f"Gefundene LeagueGroups: {len(league_group_ids)}")

    print(f"Bereits vorhandene überspringen: {SKIP_EXISTING}")

    # -----------------------------------------------------------------------
    # Sync einmal erzeugen und für alle Gruppen wiederverwenden
    # -----------------------------------------------------------------------

    sync = LeagueTableSync()

    imported_count = 0
    skipped_count = 0
    failed_count = 0

    failed_groups: list[int] = []

    # -----------------------------------------------------------------------
    # Import
    # -----------------------------------------------------------------------

    for index, league_group_id in enumerate(
        league_group_ids,
        start=1,
    ):
        print()
        print("-" * 70)

        print(f"[{index}/{len(league_group_ids)}] LeagueGroup {league_group_id}")

        result = await import_league_group(
            sync=sync,
            league_group_id=league_group_id,
        )

        if result == "imported":
            imported_count += 1

        elif result == "skipped":
            skipped_count += 1

        else:
            failed_count += 1
            failed_groups.append(league_group_id)

        # -------------------------------------------------------------------
        # Pause zum API-Schutz.
        #
        # Auch bei fehlenden Tabellen ist eine kleine Pause unproblematisch.
        # -------------------------------------------------------------------

        if index < len(league_group_ids):
            await asyncio.sleep(REQUEST_DELAY)

    # -----------------------------------------------------------------------
    # Zusammenfassung
    # -----------------------------------------------------------------------

    print()
    print()
    print("=" * 70)
    print("IMPORT ABGESCHLOSSEN")
    print("=" * 70)

    print(f"Gefunden:       {len(league_group_ids)}")

    print(f"Importiert:     {imported_count}")

    print(f"Übersprungen:   {skipped_count}")

    print(f"Fehlgeschlagen: {failed_count}")

    if failed_groups:
        print()
        print("Fehlgeschlagene LeagueGroups:")

        for league_group_id in failed_groups:
            print(f"  {league_group_id}")


# ---------------------------------------------------------------------------
# START
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    asyncio.run(main())
