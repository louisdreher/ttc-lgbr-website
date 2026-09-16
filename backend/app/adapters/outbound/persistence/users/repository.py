from app.adapters.outbound.persistence.users.models import Role as RoleRow
from app.adapters.outbound.persistence.users.models import User as UserRow
from app.core.users.domain.user import Role, User
from sqlmodel import Session, select


def to_domain(row: UserRow) -> User:
    return User(
        id=row.id,
        email=row.email,
        name=row.name,
        password_hash=row.password_hash,
        is_active=row.is_active,
        system_key=row.system_key,
        created_at=row.created_at,
        member_id=row.member_id,
        roles=[Role(id=role.id, name=role.name) for role in row.roles],
    )


class SqlUserRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, user_id: int) -> User | None:
        row = self.session.get(UserRow, user_id)
        return to_domain(row) if row is not None else None

    def email_exists(self, email: str) -> bool:
        return (
            self.session.exec(select(UserRow.id).where(UserRow.email == email)).first()
            is not None
        )

    def save(self, user: User) -> User:
        row = self.session.get(UserRow, user.id) if user.id is not None else None
        if row is None:
            row = UserRow(
                email=user.email,
                name=user.name,
                password_hash=user.password_hash,
                is_active=user.is_active,
                system_key=user.system_key,
                created_at=user.created_at,
                member_id=user.member_id,
            )
        else:
            row.email = user.email
            row.name = user.name
            row.password_hash = user.password_hash
            row.is_active = user.is_active
            row.member_id = user.member_id
        roles = []
        for role in user.roles:
            record = self.session.get(RoleRow, role.id)
            if record is None:
                raise RuntimeError("Die zugewiesene Rolle existiert nicht mehr.")
            roles.append(record)
        row.roles = roles
        self.session.add(row)
        self.session.flush()
        user.id = row.id
        return user


class SqlRoleRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_name(self, name: str) -> Role | None:
        row = self.session.exec(select(RoleRow).where(RoleRow.name == name)).first()
        return Role(id=row.id, name=row.name) if row is not None else None

    def add(self, name: str) -> None:
        self.session.add(RoleRow(name=name))
        self.session.flush()
