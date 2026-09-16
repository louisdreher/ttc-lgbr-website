from contextlib import contextmanager

from sqlalchemy import text


class SqlCompetitionWorkerLock:
    """One scheduled sync across worker processes; released on connection loss."""

    def __init__(self, engine):
        self.engine = engine

    @contextmanager
    def acquire(self):
        if self.engine.dialect.name != "postgresql":
            raise RuntimeError(
                "Der Sync-Worker benötigt PostgreSQL für die Prozesssperre."
            )
        with self.engine.connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as connection:
            acquired = connection.execute(
                text("SELECT pg_try_advisory_lock(72105, 1)")
            ).scalar_one()
            try:
                yield acquired
            finally:
                if acquired:
                    connection.execute(text("SELECT pg_advisory_unlock(72105, 1)"))
