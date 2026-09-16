from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Delivery:
    event_id: UUID
    event_type: str
    occurred_at: datetime
    payload: dict
    attempts: int
    lock_token: UUID


@dataclass(frozen=True)
class ProcessOutboxCommand:
    limit: int = 100


@dataclass(frozen=True)
class ProcessingSummary:
    succeeded: int = 0
    failed: int = 0


@dataclass(frozen=True)
class RetryOutboxMessageCommand:
    event_id: UUID


@dataclass(frozen=True)
class GetOutboxStatusQuery:
    limit: int = 20


class PermanentDeliveryError(ValueError):
    """Unsupported or invalid message: retry only after an explicit repair."""
