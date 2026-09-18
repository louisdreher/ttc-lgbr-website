from app.adapters.outbound.persistence.auth.account_sessions import SqlAccountSessions
from app.adapters.outbound.persistence.members.repository import SqlMembers
from app.adapters.outbound.persistence.users.password_links import SqlPasswordLinks
from app.adapters.outbound.persistence.users.repository import (
    SqlRoleRepository,
    SqlUserRepository,
)
from sqlmodel import Session


class SqlUserUnitOfWork:
    def __init__(self, session: Session):
        self.session = session
        self.users = SqlUserRepository(session)
        self.roles = SqlRoleRepository(session)
        self.members = SqlMembers(session)
        self.links = SqlPasswordLinks(session)
        self.sessions = SqlAccountSessions(session)
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
