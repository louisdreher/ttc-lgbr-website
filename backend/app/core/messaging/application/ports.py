from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

from app.core.messaging.application.dto import Delivery


class OutboxStore(Protocol):
    def claim(
        self, now: datetime, lease: timedelta, max_attempts: int
    ) -> Delivery | None: ...
    def complete(self, delivery: Delivery, now: datetime) -> bool: ...
    def fail(
        self,
        delivery: Delivery,
        now: datetime,
        error: str,
        next_attempt_at: datetime | None,
    ) -> bool: ...


class MessageHandler(Protocol):
    def handle(self, delivery: Delivery) -> None: ...


class OutboxOperations(Protocol):
    def retry(self, event_id: UUID, now: datetime) -> None: ...
    def status(self, limit: int) -> list[dict]: ...
