from app.adapters.outbound.persistence.messaging.models import OutboxMessage
from app.core.competition.application.events import TeamMatchResultsImported
from sqlmodel import Session


class SqlCompetitionEventOutbox:
    def __init__(self, session: Session):
        self.session = session

    def add(self, event: TeamMatchResultsImported) -> None:
        event_type = "competition.team_match_results_imported.v1"
        self.session.add(
            OutboxMessage(
                event_id=event.event_id,
                event_type=event_type,
                deduplication_key=f"{event_type}:{event.team_match_id}",
                occurred_at=event.occurred_at,
                payload={
                    "team_match_id": event.team_match_id,
                    "import_origin": event.import_origin.value,
                },
            )
        )
        # The enclosing Competition unit of work owns commit and rollback.
        self.session.flush()
