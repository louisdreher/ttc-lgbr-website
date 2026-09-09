from sqlmodel import Session

from app.adapters.outbound.persistence.users.unit_of_work import SqlUserUnitOfWork
from app.adapters.outbound.security.passwords import ArgonPasswords
from app.core.users.application.commands import (
    AddUserRole,
    CreateUser,
    EnsureDefaultRoles,
    RemoveUserRole,
)


def build_create_user(session: Session) -> CreateUser:
    return CreateUser(SqlUserUnitOfWork(session), ArgonPasswords())


def build_add_user_role(session: Session) -> AddUserRole:
    return AddUserRole(SqlUserUnitOfWork(session))


def build_remove_user_role(session: Session) -> RemoveUserRole:
    return RemoveUserRole(SqlUserUnitOfWork(session))


def build_ensure_default_roles(session: Session) -> EnsureDefaultRoles:
    return EnsureDefaultRoles(SqlUserUnitOfWork(session))
