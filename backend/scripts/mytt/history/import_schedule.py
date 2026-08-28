import argparse
import asyncio

from app.domains.competition.season.model import SeasonHalf
from app.integrations.mytischtennis.sync.schedule import (
    ScheduleSync,
)

async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Importiert den myTT-Spielplan einer historischen Halbserie."
    )
    parser.add_argument("start_year", type=int)
    parser.add_argument("end_year", type=int)
    parser.add_argument("half", type=SeasonHalf, choices=list(SeasonHalf))
    args = parser.parse_args()

    sync = ScheduleSync()

    await sync.sync(
        start_year=args.start_year,
        end_year=args.end_year,
        half=args.half,
    )


if __name__ == "__main__":
    asyncio.run(main())
