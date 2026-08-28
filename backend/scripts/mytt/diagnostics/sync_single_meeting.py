import argparse
import asyncio

from app.integrations.mytischtennis.sync.meeting import (
    MeetingSync,
)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Synchronisiert eine einzelne myTischtennis-Begegnung."
    )
    parser.add_argument("meeting_id", type=int, help="myTT-Begegnungs-ID")
    args = parser.parse_args()

    sync = MeetingSync()

    await sync.sync_by_meeting_id(
        meeting_id=args.meeting_id,
    )


if __name__ == "__main__":
    asyncio.run(main())
