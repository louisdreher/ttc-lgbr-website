from datetime import datetime

from app.adapters.outbound.persistence.auth.models import RefreshSession
from sqlmodel import Session, delete, update


class SqlAccountSessions:
    """Implements the Users-owned session invalidation port in the same transaction."""

    def __init__(self, session: Session):
        self.session = session

    def revoke(self, user_id: int, now: datetime) -> None:
        self.session.exec(
            update(RefreshSession)
            .where(RefreshSession.user_id == user_id)
            .values(revoked_at=now)
        )

    def delete(self, user_id: int) -> None:
        self.session.exec(
            delete(RefreshSession).where(RefreshSession.user_id == user_id)
        )
