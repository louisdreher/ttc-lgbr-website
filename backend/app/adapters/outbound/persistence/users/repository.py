from app.adapters.outbound.persistence.users.models import Role as RoleRow
from app.adapters.outbound.persistence.users.models import User as UserRow
from app.core.users.application.errors import UserConflictError
from app.core.users.domain.user import Role, User
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert as postgres_insert
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
        auth_invalid_before=row.auth_invalid_before,
        roles=[Role(id=role.id, name=role.name) for role in row.roles],
    )


class SqlUserRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, user_id: int) -> User | None:
        row = self.session.get(UserRow, user_id)
        return to_domain(row) if row is not None else None

    def lock_administration(self) -> None:
        # All account/role/link mutations serialize on the stable ADMIN role row.
        # Refresh objects read earlier by authorization after acquiring the lock.
        self.session.exec(
            select(RoleRow).where(RoleRow.name == "ADMIN").with_for_update()
        ).all()
        self.session.expire_all()

    def active_admin_count(self) -> int:
        return len(
            self.session.exec(
                select(UserRow).where(
                    UserRow.is_active.is_(True),
                    UserRow.system_key.is_(None),
                    UserRow.roles.any(RoleRow.name == "ADMIN"),
                )
            ).all()
        )

    def admin_exists(self) -> bool:
        # Even a disabled administrator prevents re-running first-time setup.
        return self.session.exec(
            select(UserRow.id).where(UserRow.roles.any(RoleRow.name == "ADMIN"))
        ).first() is not None

    def member_in_use(self, member_id: int, user_id: int | None) -> bool:
        query = select(UserRow.id).where(UserRow.member_id == member_id)
        if user_id is not None:
            query = query.where(UserRow.id != user_id)
        return self.session.exec(query).first() is not None

    def delete(self, user: User) -> None:
        # FK inserts take KEY SHARE on this row. Lock it before checking references
        # so a concurrent content insert cannot lose attribution via SET NULL.
        row = self.session.exec(
            select(UserRow).where(UserRow.id == user.id).with_for_update()
        ).one()
        # Preserve attribution even for references whose FK uses ON DELETE SET NULL.
        # Authentication and role records are deliberately removed with the account.
        for table in UserRow.metadata.tables.values():
            if table.name in {"userrolelink", "refreshsession", "password_link"}:
                continue
            for fk in table.foreign_keys:
                if fk.target_fullname == "user.id":
                    reference = self.session.execute(
                        select(fk.parent).where(fk.parent == user.id).limit(1)
                    ).first()
                    if reference is not None:
                        raise UserConflictError(
                            "Das Konto ist mit Inhalten verknüpft. Bitte stattdessen deaktivieren."
                        )
        self.session.delete(row)
        try:
            self.session.flush()
        except IntegrityError as error:
            raise UserConflictError(
                "Das Konto ist mit Inhalten verknüpft. Bitte stattdessen deaktivieren."
            ) from error

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
                auth_invalid_before=user.auth_invalid_before,
            )
        else:
            row.email = user.email
            row.name = user.name
            row.password_hash = user.password_hash
            row.is_active = user.is_active
            row.member_id = user.member_id
            row.auth_invalid_before = user.auth_invalid_before
        roles = []
        for role in user.roles:
            record = self.session.get(RoleRow, role.id)
            if record is None:
                raise RuntimeError("Die zugewiesene Rolle existiert nicht mehr.")
            roles.append(record)
        row.roles = roles
        self.session.add(row)
        try:
            self.session.flush()
        except IntegrityError as error:
            raise UserConflictError(
                "E-Mail oder Mitglied ist bereits einem Konto zugeordnet."
            ) from error
        user.id = row.id
        return user


class SqlRoleRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_name(self, name: str) -> Role | None:
        row = self.session.exec(select(RoleRow).where(RoleRow.name == name)).first()
        return Role(id=row.id, name=row.name) if row is not None else None

    def add(self, name: str) -> None:
        if self.session.get_bind().dialect.name == "postgresql":
            # Another startup may have inserted the role after our initial read.
            self.session.execute(
                postgres_insert(RoleRow)
                .values(name=name)
                .on_conflict_do_nothing(index_elements=["name"])
            )
            return
        self.session.add(RoleRow(name=name))
        self.session.flush()
