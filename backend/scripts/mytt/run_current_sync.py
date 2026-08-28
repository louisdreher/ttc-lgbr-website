import argparse
import asyncio
import traceback

from app.integrations.mytischtennis.current_season import CurrentSeasonSync


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Startet einen Teil der aktuellen myTT-Synchronisierung."
    )

    parser.add_argument(
        "sync_type",
        choices=[
            "schedule",
            "meetings",
            "tables",
            "registrations",
        ],
        help="Welcher Sync gestartet werden soll.",
    )

    args = parser.parse_args()

    sync = CurrentSeasonSync()

    print()
    print("=" * 70)
    print(f"SYNC: {args.sync_type.upper()}")
    print("=" * 70)

    try:
        if args.sync_type == "schedule":
            await sync.sync_schedule()

        elif args.sync_type == "meetings":
            await sync.sync_new_meetings()

        elif args.sync_type == "tables":
            await sync.sync_league_tables()

        elif args.sync_type == "registrations":
            await sync.sync_registrations()

    except Exception:
        print()
        print("=" * 70)
        print("SYNC FEHLGESCHLAGEN")
        print("=" * 70)

        traceback.print_exc()

        return

    print()
    print("=" * 70)
    print("SYNC ERFOLGREICH ABGESCHLOSSEN")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
