from app.adapters.outbound.persistence.users.models import PasswordLink as LinkRow
from app.core.users.domain.password_link import PasswordLink
from sqlmodel import Session, delete, select


class SqlPasswordLinks:
    def __init__(self, session: Session):
        self.session = session

    def replace(self, link: PasswordLink) -> None:
        self.delete_for_user(link.user_id)
        self.session.add(
            LinkRow(
                user_id=link.user_id,
                token_hash=link.token_hash,
                expires_at=link.expires_at,
            )
        )
        self.session.flush()

    def get(self, token_hash: str) -> PasswordLink | None:
        row = self.session.exec(
            select(LinkRow).where(LinkRow.token_hash == token_hash)
        ).first()
        return PasswordLink(**row.model_dump()) if row else None

    def delete_for_user(self, user_id: int) -> None:
        self.session.exec(delete(LinkRow).where(LinkRow.user_id == user_id))
