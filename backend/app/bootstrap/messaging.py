from datetime import datetime, timezone

from app.adapters.inbound.messaging.match_reports import MatchResultsImportedHandler
from app.adapters.outbound.persistence.database import engine
from app.adapters.outbound.persistence.messaging.store import SqlOutboxStore
from app.bootstrap.articles import build_create_match_report_draft
from app.bootstrap.settings import settings
from app.core.messaging.application.commands import ProcessOutbox, RetryOutboxMessage
from app.core.messaging.application.queries import GetOutboxStatus


def build_retry_outbox_message():
    return RetryOutboxMessage(
        SqlOutboxStore(lambda: Session(engine)), lambda: datetime.now(timezone.utc)
    )


def build_get_outbox_status():
    return GetOutboxStatus(SqlOutboxStore(lambda: Session(engine)))


from sqlmodel import Session


def build_process_outbox(*, session_factory=None, clock=None, generator=None):
    factory = session_factory or (lambda: Session(engine))
    return ProcessOutbox(
        SqlOutboxStore(factory),
        MatchResultsImportedHandler(
            factory,
            lambda session: build_create_match_report_draft(
                session,
                session_factory=factory,
                generator=generator,
            ),
        ),
        clock or (lambda: datetime.now(timezone.utc)),
        max_attempts=settings.outbox_max_attempts,
        lease_seconds=settings.outbox_lease_seconds,
        retry_seconds=settings.outbox_retry_seconds,
    )
