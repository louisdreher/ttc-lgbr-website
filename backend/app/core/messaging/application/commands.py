import logging
from collections.abc import Callable
from datetime import datetime, timedelta

from app.core.messaging.application.dto import (
    PermanentDeliveryError,
    ProcessingSummary,
    ProcessOutboxCommand,
    RetryOutboxMessageCommand,
)
from app.core.messaging.application.ports import (
    MessageHandler,
    OutboxOperations,
    OutboxStore,
)

logger = logging.getLogger(__name__)


class RetryOutboxMessage:
    def __init__(self, store: OutboxOperations, clock: Callable[[], datetime]):
        self.store, self.clock = store, clock

    def execute(self, command: RetryOutboxMessageCommand) -> None:
        # The store atomically checks the reservation before releasing the message.
        self.store.retry(command.event_id, self.clock())


class ProcessOutbox:
    def __init__(
        self,
        store: OutboxStore,
        handler: MessageHandler,
        clock: Callable[[], datetime],
        *,
        max_attempts: int = 5,
        lease_seconds: int = 300,
        retry_seconds: int = 60,
    ):
        if min(max_attempts, lease_seconds, retry_seconds) < 1:
            raise ValueError(
                "Versuche, Reservierungsdauer und Wartezeit müssen positiv sein."
            )
        self.store, self.handler, self.clock = store, handler, clock
        self.max_attempts = max_attempts
        self.lease = timedelta(seconds=lease_seconds)
        self.retry_seconds = retry_seconds

    def execute(self, command: ProcessOutboxCommand) -> ProcessingSummary:
        if command.limit < 1:
            raise ValueError("Das Verarbeitungslimit muss positiv sein.")
        succeeded = failed = 0
        for _ in range(command.limit):
            delivery = self.store.claim(self.clock(), self.lease, self.max_attempts)
            if delivery is None:
                break
            try:
                self.handler.handle(delivery)
            except Exception as error:  # noqa: BLE001 -- persist each handler failure for retry
                now = self.clock()
                terminal = (
                    isinstance(error, PermanentDeliveryError)
                    or delivery.attempts >= self.max_attempts
                )
                delay = min(
                    self.retry_seconds * 2 ** min(delivery.attempts - 1, 16), 3600
                )
                next_attempt = None if terminal else now + timedelta(seconds=delay)
                # Do not persist arbitrary exception text that may contain SQL parameters.
                detail = (
                    str(error)
                    if isinstance(error, PermanentDeliveryError)
                    else type(error).__name__
                )
                self.store.fail(delivery, now, detail[:1000], next_attempt)
                logger.error(
                    "Outbox-Verarbeitung fehlgeschlagen: event_id=%s error=%s attempt=%s",
                    delivery.event_id,
                    type(error).__name__,
                    delivery.attempts,
                )
                failed += 1
            else:
                if self.store.complete(delivery, self.clock()):
                    succeeded += 1
                else:
                    # A different worker owns a newer lease; its acknowledgement wins.
                    logger.warning(
                        "Outbox-Reservierung nicht mehr aktuell: event_id=%s",
                        delivery.event_id,
                    )
        return ProcessingSummary(succeeded, failed)
