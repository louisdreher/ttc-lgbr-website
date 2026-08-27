import asyncio

from app.integrations.mytischtennis.sync.schedule import (
    ScheduleSync,
)

from backend.app.domains.competition.teams.model import SeasonHalf

PERIODS = [
    # (2009, 2010, SeasonHalf.RR),
    # (2010, 2011, SeasonHalf.RR),
    # (2011, 2012, SeasonHalf.RR),
    # (2015, 2016, SeasonHalf.VR),
    # (2015, 2016, SeasonHalf.RR),
    # (2016, 2017, SeasonHalf.RR),
    # (2017, 2018, SeasonHalf.RR),
    (2018, 2019, SeasonHalf.VR),
    # (2019, 2020, SeasonHalf.RR),
    # (2020, 2021, SeasonHalf.RR),
    # (2021, 2022, SeasonHalf.RR),
    # (2023, 2024, SeasonHalf.RR),
    # (2024, 2025, SeasonHalf.RR),
]


async def main():

    sync = ScheduleSync()

    for start_year, end_year, half in PERIODS:
        await sync.sync(
            start_year=start_year,
            end_year=end_year,
            half=half,
        )

        await asyncio.sleep(0.5)


if __name__ == "__main__":
    asyncio.run(main())
