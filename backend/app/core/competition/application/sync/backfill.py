from app.core.competition.application.sync.dto import BackfillMatchEventsCommand
from app.core.competition.application.sync.ports import SyncUnitOfWork


class BackfillMatchEvents:
    def __init__(self, uow: SyncUnitOfWork):
        self.uow = uow

    def execute(self, command: BackfillMatchEventsCommand) -> tuple[int, int]:
        created = updated = 0
        with self.uow:
            for match_id in self.uow.repository.match_ids(
                completed_only=command.completed_only
            ):
                if self.uow.events.synchronize(match_id):
                    created += 1
                else:
                    updated += 1
            self.uow.commit()
        return created, updated
