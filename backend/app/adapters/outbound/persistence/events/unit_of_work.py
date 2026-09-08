from sqlmodel import Session

from app.adapters.outbound.persistence.events.repository import (
    SqlCategoryRepository,
    SqlEventRepository,
)


class SqlEventUnitOfWork:
    """The request owns the session; this adapter owns commit/rollback."""

    def __init__(self, session: Session):
        self.session = session
        self.events = SqlEventRepository(session)
        self.categories = SqlCategoryRepository(session)
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
