from app.adapters.inbound.cli.content_worker import ContentWorker
from app.adapters.outbound.persistence.competition.worker_lock import (
    SqlCompetitionWorkerLock,
)
from app.adapters.outbound.persistence.database import engine
from app.bootstrap.competition_sync import build_competition
from app.bootstrap.messaging import build_process_outbox
from app.bootstrap.settings import settings
from app.core.competition.application.sync.dto import SyncCurrentCommand
from app.core.messaging.application.dto import ProcessOutboxCommand


def build_content_worker():
    sync = build_competition().current
    processor = build_process_outbox()
    return ContentWorker(
        lambda: sync.execute(SyncCurrentCommand("meetings")),
        lambda: processor.execute(ProcessOutboxCommand(settings.outbox_batch_size)),
        SqlCompetitionWorkerLock(engine),
        sync_interval=settings.competition_sync_interval_seconds,
        poll_interval=settings.outbox_poll_interval_seconds,
    )
