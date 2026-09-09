from dataclasses import asdict
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import update
from sqlmodel import Session, select

from app.adapters.outbound.persistence.auth.models import RefreshSession as SessionRow
from app.core.auth.domain.session import RefreshSession


class SqlRefreshSessionRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_for_update(self, token_hash: str) -> RefreshSession | None:
        # PostgreSQL serializes competing rotations of the same token here.
        row = self.session.exec(
            select(SessionRow)
            .where(SessionRow.token_hash == token_hash)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).first()
        if row is None:
            return None
        values = row.model_dump()
        for name, value in values.items():
            # SQLite test storage loses timezone metadata; PostgreSQL retains it.
            if isinstance(value, datetime) and value.tzinfo is None:
                values[name] = value.replace(tzinfo=timezone.utc)
        return RefreshSession(**values)

    def save(self, session: RefreshSession) -> None:
        row = self.session.get(SessionRow, session.id)
        if row is None:
            row = SessionRow(**asdict(session))
        else:
            row.sqlmodel_update(asdict(session))
        self.session.add(row)
        self.session.flush()

    def revoke_family(self, family_id: UUID, now: datetime) -> None:
        self.session.execute(
            update(SessionRow)
            .where(
                SessionRow.family_id == family_id,
                SessionRow.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
