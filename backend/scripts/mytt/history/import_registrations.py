import argparse
import asyncio
import json

import httpx
from app.core.database import engine
from app.domains.competition.league.model import LeagueGroup
from app.domains.competition.season.model import Season, SeasonHalf
from app.integrations.mytischtennis.sync.registrations import (
    RegistrationsSync,
)
from sqlmodel import Session, select

# ---------------------------------------------------------------------------
# EINSTELLUNGEN
# ---------------------------------------------------------------------------

MAX_RETRIES = 2

DELAY_BETWEEN_ATTEMPTS = 2.0
DELAY_BETWEEN_GROUPS = 1.0


# ---------------------------------------------------------------------------
# SEASONS EINES KALENDERJAHRES
#
# Beispiel 2010:
#
# Januar - Juni:
#   Saison 2009/10 RR
#
# Juli - Dezember:
#   Saison 2010/11 VR
# ---------------------------------------------------------------------------


def get_seasons_for_year(
    year: int,
) -> list[tuple[int, int, SeasonHalf]]:
    return [
        (
            year - 1,
            year,
            SeasonHalf.RR,
        ),
        (
            year,
            year + 1,
            SeasonHalf.VR,
        ),
    ]


# ---------------------------------------------------------------------------
# IMPORT EINER LEAGUEGROUP
# ---------------------------------------------------------------------------


async def import_league_group(
    registration_sync: RegistrationsSync,
    league_group_id: int,
) -> str:

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):
        try:
            imported = await registration_sync.sync(
                league_group_id=league_group_id,
            )

            if imported:
                return "imported"

            return "skipped"

        # -------------------------------------------------------------------
        # Temporäre/API-Fehler erneut versuchen
        # -------------------------------------------------------------------

        except (
            httpx.HTTPError,
            json.JSONDecodeError,
        ) as exc:
            print(
                f"LeagueGroup {league_group_id}: "
                f"temporärer Fehler "
                f"(Versuch {attempt}/{MAX_RETRIES})"
            )

            print(f"  {type(exc).__name__}: {exc}")

            if attempt >= MAX_RETRIES:
                return "failed"

            print(f"  Neuer Versuch in {DELAY_BETWEEN_ATTEMPTS} Sekunden ...")

            await asyncio.sleep(DELAY_BETWEEN_ATTEMPTS)

        # -------------------------------------------------------------------
        # Daten-/Programmierfehler nicht mehrfach versuchen
        # -------------------------------------------------------------------

        except Exception as exc:
            print(f"LeagueGroup {league_group_id}: FEHLER")

            print(f"  {type(exc).__name__}: {exc}")

            return "failed"

    return "failed"


# ---------------------------------------------------------------------------
# HAUPTPROGRAMM
# ---------------------------------------------------------------------------


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Importiert historische Mannschaftsmeldungen."
    )
    parser.add_argument("start_year", type=int, help="Erstes Kalenderjahr")
    parser.add_argument("end_year", type=int, help="Letztes Kalenderjahr")
    args = parser.parse_args()

    if args.end_year < args.start_year:
        parser.error("end_year darf nicht vor start_year liegen")

    registration_sync = RegistrationsSync()

    imported_count = 0
    skipped_count = 0
    failed_count = 0

    failed_groups: list[int] = []

    # -----------------------------------------------------------------------
    # Kalenderjahre durchlaufen
    #
    # Beispiel 2010:
    #
    # Januar - Juni:
    #   2009/10 RR
    #
    # Juli - Dezember:
    #   2010/11 VR
    # -----------------------------------------------------------------------

    for year in range(
        args.start_year,
        args.end_year + 1,
    ):
        seasons = get_seasons_for_year(year)

        for (
            season_start_year,
            season_end_year,
            half,
        ) in seasons:
            print()
            print("=" * 70)
            print("HISTORICAL REGISTRATION IMPORT")
            print("=" * 70)

            print(
                f"Saison: "
                f"{season_start_year}/"
                f"{str(season_end_year)[-2:]} "
                f"{half.value.upper()}"
            )

            # ----------------------------------------------------------------
            # Passende Season und deren LeagueGroups laden
            # ----------------------------------------------------------------

            with Session(engine) as session:
                season = session.exec(
                    select(Season).where(
                        Season.start_year == season_start_year,
                        Season.end_year == season_end_year,
                        Season.half == half,
                    )
                ).first()

                if season is None:
                    print("Season nicht in der DB vorhanden.")

                    continue

                league_groups = session.exec(
                    select(LeagueGroup)
                    .where(LeagueGroup.season_id == season.id)
                    .order_by(LeagueGroup.id)
                ).all()

                league_group_ids = [
                    league_group.id
                    for league_group in league_groups
                    if league_group.id is not None
                ]

            print(f"LeagueGroups: {len(league_group_ids)}")

            # ----------------------------------------------------------------
            # Jede LeagueGroup separat synchronisieren
            # ----------------------------------------------------------------

            for index, league_group_id in enumerate(
                league_group_ids,
                start=1,
            ):
                print()

                print(
                    f"[{index}/{len(league_group_ids)}] LeagueGroup {league_group_id}"
                )

                result = await import_league_group(
                    registration_sync=registration_sync,
                    league_group_id=league_group_id,
                )

                if result == "imported":
                    imported_count += 1

                elif result == "skipped":
                    skipped_count += 1

                else:
                    failed_count += 1

                    failed_groups.append(league_group_id)

                await asyncio.sleep(DELAY_BETWEEN_GROUPS)

    # -----------------------------------------------------------------------
    # Zusammenfassung
    # -----------------------------------------------------------------------

    print()
    print("=" * 70)
    print("IMPORT ABGESCHLOSSEN")
    print("=" * 70)

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
