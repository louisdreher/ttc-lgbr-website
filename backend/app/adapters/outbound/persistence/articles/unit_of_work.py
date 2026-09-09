from sqlmodel import Session

from app.adapters.outbound.persistence.articles.repository import (
    SQLModelArticleRepository,
)


class SqlArticleUnitOfWork:
    """Owns the write transaction; the caller owns the session lifetime."""

    def __init__(self, session: Session):
        self.session = session
        self.articles = SQLModelArticleRepository(session)
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
