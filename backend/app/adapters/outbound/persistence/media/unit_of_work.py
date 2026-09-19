from sqlmodel import Session

from app.adapters.outbound.persistence.media.repository import SqlMediaRepository


class SqlMediaUnitOfWork:
    """Own the transaction; the caller supplies a dedicated upload session."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.media = SqlMediaRepository(session)
        self._committed = False

    def __enter__(self):
        self._committed = False
        return self

    def commit(self) -> None:
        self.session.commit()
        self._committed = True

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if exc_type is not None or not self._committed:
            self.session.rollback()
