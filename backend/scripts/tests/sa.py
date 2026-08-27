import asyncio

from app.integrations.mytischtennis.sync.league_table import (
    LeagueTableSync,
)


async def main():
    sync = LeagueTableSync()

    await sync.sync(
        league_group_id=510,
    )


if __name__ == "__main__":
    asyncio.run(main())
