"""Run sync and outbox polling independently of FastAPI and of each other."""

import asyncio
import logging

logger = logging.getLogger(__name__)


class ContentWorker:
    def __init__(
        self,
        sync,
        process,
        lock,
        *,
        sync_interval: int,
        poll_interval: int,
        sleep=asyncio.sleep,
    ):
        if min(sync_interval, poll_interval) <= 0:
            raise ValueError("Worker-Intervalle müssen positiv sein.")
        self.sync, self.process, self.lock = sync, process, lock
        self.sync_interval, self.poll_interval, self.sleep = (
            sync_interval,
            poll_interval,
            sleep,
        )

    async def sync_once(self) -> bool:
        try:
            with self.lock.acquire() as acquired:
                if not acquired:
                    return True
                summary = await self.sync()
            if summary.failed:
                logger.error(
                    "Spiel-Sync mit Fehlern abgeschlossen: ids=%s", summary.failed
                )
                return False
            logger.info(
                "Spiel-Sync abgeschlossen: imported=%s skipped=%s",
                summary.imported,
                summary.skipped,
            )
            return True
        except Exception as error:  # noqa: BLE001 -- isolate a failed scheduled run
            logger.error("Spiel-Sync fehlgeschlagen: %s", type(error).__name__)
            return False

    async def process_once(self) -> bool:
        try:
            summary = await asyncio.to_thread(self.process)
            if summary.succeeded or summary.failed:
                logger.info(
                    "Outbox verarbeitet: succeeded=%s failed=%s",
                    summary.succeeded,
                    summary.failed,
                )
            return summary.failed == 0
        except Exception as error:  # noqa: BLE001 -- keep polling after storage failures
            logger.error("Outbox-Abruf fehlgeschlagen: %s", type(error).__name__)
            return False

    async def once(self) -> bool:
        sync_ok = await self.sync_once()
        outbox_ok = await self.process_once()
        return sync_ok and outbox_ok

    async def run(self) -> None:
        async def repeat(operation, interval):
            while True:
                await operation()
                await self.sleep(interval)

        await asyncio.gather(
            repeat(self.sync_once, self.sync_interval),
            repeat(self.process_once, self.poll_interval),
        )
