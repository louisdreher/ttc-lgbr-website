from app.core.messaging.application.dto import GetOutboxStatusQuery
from app.core.messaging.application.ports import OutboxOperations


class GetOutboxStatus:
    def __init__(self, store: OutboxOperations):
        self.store = store

    def execute(self, query: GetOutboxStatusQuery) -> list[dict]:
        if not 1 <= query.limit <= 1000:
            raise ValueError("Limit muss zwischen 1 und 1000 liegen.")
        return self.store.status(query.limit)
