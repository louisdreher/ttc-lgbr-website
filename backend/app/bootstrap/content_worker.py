from app.adapters.inbound.cli.content_worker import ContentWorker
from app.adapters.outbound.persistence.competition.worker_lock import (
    SqlCompetitionWorkerLock,
)
from app.adapters.outbound.persistence.database import engine
from app.bootstrap.competition_automation import (
    build_scheduled_sync,
    build_worker_heartbeat,
)
from app.bootstrap.messaging import build_process_outbox
from app.bootstrap.settings import settings
from app.core.messaging.application.dto import ProcessOutboxCommand


def build_content_worker():
    sync = build_scheduled_sync()
    processor = build_process_outbox()
    return ContentWorker(
        sync.execute,
        lambda: processor.execute(ProcessOutboxCommand(settings.outbox_batch_size)),
        SqlCompetitionWorkerLock(engine),
        sync_interval=15,
        poll_interval=settings.outbox_poll_interval_seconds,
        heartbeat=build_worker_heartbeat().execute,
    )
