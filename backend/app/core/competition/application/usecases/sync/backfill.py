from app.core.competition.application.dto import BackfillMatchEventsCommand
from app.core.competition.application.ports import CompetitionUnitOfWork


class BackfillMatchEvents:
    def __init__(self, uow: CompetitionUnitOfWork):
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
