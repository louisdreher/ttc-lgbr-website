"""Compatibility entry point; import logic lives in Competition use cases."""

import asyncio

from app.adapters.inbound.cli.competition import main as run_import


async def main():
    await run_import("meetings")


if __name__ == "__main__":
    asyncio.run(main())
