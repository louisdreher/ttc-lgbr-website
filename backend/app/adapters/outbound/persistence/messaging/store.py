from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from app.adapters.outbound.persistence.messaging.models import OutboxMessage
from app.core.messaging.application.dto import Delivery
from sqlalchemy import or_, update
from sqlmodel import select


def aware(value):
    return (
        value.replace(tzinfo=timezone.utc)
        if value is not None and value.tzinfo is None
        else value
    )


class SqlOutboxStore:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def claim(
        self, now: datetime, lease: timedelta, max_attempts: int
    ) -> Delivery | None:
        with self.session_factory() as session:
            while True:
                row = session.exec(
                    select(OutboxMessage)
                    .where(
                        OutboxMessage.processed_at.is_(None),
                        OutboxMessage.failed_at.is_(None),
                        or_(
                            OutboxMessage.next_attempt_at.is_(None),
                            OutboxMessage.next_attempt_at <= now,
                        ),
                        or_(
                            OutboxMessage.locked_until.is_(None),
                            OutboxMessage.locked_until <= now,
                        ),
                    )
                    .order_by(OutboxMessage.occurred_at, OutboxMessage.event_id)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                ).first()
                if row is None:
                    session.commit()
                    return None
                if row.attempts >= max_attempts:
                    row.failed_at = now
                    row.locked_until = row.lock_token = None
                    row.last_error = (
                        "Maximale Versuche nach abgelaufener Reservierung erreicht."
                    )
                    session.add(row)
                    session.flush()
                    continue
                row.attempts += 1
                row.lock_token = uuid4()
                row.locked_until = now + lease
                session.add(row)
                delivery = Delivery(
                    row.event_id,
                    row.event_type,
                    aware(row.occurred_at),
                    row.payload,
                    row.attempts,
                    row.lock_token,
                )
                session.commit()
                return delivery

    def _finish(self, delivery: Delivery, **values) -> bool:
        with self.session_factory() as session:
            result = session.execute(
                update(OutboxMessage)
                .where(
                    OutboxMessage.event_id == delivery.event_id,
                    OutboxMessage.lock_token == delivery.lock_token,
                    OutboxMessage.processed_at.is_(None),
                )
                .values(lock_token=None, locked_until=None, **values)
            )
            session.commit()
            return result.rowcount == 1

    def complete(self, delivery: Delivery, now: datetime) -> bool:
        return self._finish(
            delivery, processed_at=now, last_error=None, next_attempt_at=None
        )

    def fail(
        self,
        delivery: Delivery,
        now: datetime,
        error: str,
        next_attempt_at: datetime | None,
    ) -> bool:
        return self._finish(
            delivery,
            last_error=error,
            next_attempt_at=next_attempt_at,
            failed_at=now if next_attempt_at is None else None,
        )

    def retry(self, event_id: UUID, now: datetime) -> None:
        with self.session_factory() as session:
            row = session.exec(
                select(OutboxMessage)
                .where(OutboxMessage.event_id == event_id)
                .with_for_update()
            ).first()
            if row is None:
                raise ValueError("Nachricht nicht gefunden.")
            if row.processed_at is not None:
                raise ValueError("Nachricht ist bereits verarbeitet.")
            if row.locked_until is not None and aware(row.locked_until) > now:
                raise ValueError("Nachricht wird gerade verarbeitet.")
            row.attempts = 0
            row.failed_at = row.locked_until = row.lock_token = None
            row.next_attempt_at = now
            session.add(row)
            session.commit()

    def status(self, limit: int = 20) -> list[dict]:
        if not 1 <= limit <= 1000:
            raise ValueError("Limit muss zwischen 1 und 1000 liegen.")
        with self.session_factory() as session:
            rows = session.exec(
                select(OutboxMessage)
                .order_by(OutboxMessage.occurred_at.desc())
                .limit(limit)
            ).all()
            return [row.model_dump(exclude={"payload", "lock_token"}) for row in rows]
