from app.integrations.mytischtennis.sync.current import CurrentSync
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()


async def sync_meetings():
    sync = CurrentSync()
    await sync.sync_new_meetings()


async def sync_tables():
    sync = CurrentSync()
    await sync.sync_league_tables()


async def sync_registrations():
    sync = CurrentSync()
    await sync.sync_registrations()


scheduler.add_job(
    sync_meetings,
    "interval",
    hours=2,
)

scheduler.add_job(
    sync_tables,
    "cron",
    hour=3,
)

scheduler.add_job(
    sync_registrations,
    "cron",
    day_of_week="sun",
    hour=4,
)
