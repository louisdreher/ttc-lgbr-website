from sqlmodel import Session, select

from app.adapters.outbound.persistence.users.models import User
from app.core.users.application.dto import UserCredentials, UserDetails
from app.core.users.domain.user import normalize_email


class SqlUserReader:
    def __init__(self, session: Session):
        self.session = session

    def get_public(self, user_id: int) -> UserDetails | None:
        user = self.session.get(User, user_id)
        if user is None:
            return None
        return UserDetails(
            id=user.id,
            email=user.email,
            name=user.name,
            is_active=user.is_active,
            roles=[role.name for role in user.roles],
        )

    def get_credentials(self, email: str) -> UserCredentials | None:
        user = self.session.exec(
            select(User).where(User.email == normalize_email(email))
        ).first()
        if user is None:
            return None
        return UserCredentials(
            user_id=user.id, password_hash=user.password_hash, is_active=user.is_active
        )

    def get_names(self, user_ids: set[int]) -> dict[int, str]:
        if not user_ids:
            return {}
        return dict(
            self.session.exec(
                select(User.id, User.name).where(User.id.in_(user_ids))
            ).all()
        )
