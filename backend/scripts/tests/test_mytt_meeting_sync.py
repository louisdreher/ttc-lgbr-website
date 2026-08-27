import asyncio

from app.integrations.mytischtennis.sync.meeting import (
    MeetingSync,
)


MEETING_ID = 8269927


async def main():

    sync = MeetingSync()

    await sync.sync_by_meeting_id(
        meeting_id=MEETING_ID,
    )


if __name__ == "__main__":
    asyncio.run(main())