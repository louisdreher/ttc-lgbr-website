from typing import Annotated

from app.adapters.outbound.persistence.database import get_session
from app.bootstrap import users as wiring
from app.core.users.application.commands import (
    AddUserRole,
    CreateUser,
    DeleteUser,
    RemoveUserRole,
    SaveManagedUser,
    SendPasswordLink,
    SetPassword,
    SetUserActive,
)
from app.core.users.application.queries import (
    GetManagedUser,
    GetMember,
    ListMemberOptions,
    ListUsers,
)
from fastapi import Depends
from sqlmodel import Session


def provide_create_user(
    session: Annotated[Session, Depends(get_session)],
) -> CreateUser:
    return wiring.build_create_user(session)


def provide_add_user_role(
    session: Annotated[Session, Depends(get_session)],
) -> AddUserRole:
    return wiring.build_add_user_role(session)


def provide_remove_user_role(
    session: Annotated[Session, Depends(get_session)],
) -> RemoveUserRole:
    return wiring.build_remove_user_role(session)


SessionDependency = Annotated[Session, Depends(get_session)]


def provide_save_managed_user(session: SessionDependency) -> SaveManagedUser:
    return wiring.build_save_managed_user(session)


def provide_set_user_active(session: SessionDependency) -> SetUserActive:
    return wiring.build_set_user_active(session)


def provide_delete_user(session: SessionDependency) -> DeleteUser:
    return wiring.build_delete_user(session)


def provide_list_users(session: SessionDependency) -> ListUsers:
    return wiring.build_list_users(session)


def provide_get_managed_user(session: SessionDependency) -> GetManagedUser:
    return wiring.build_get_managed_user(session)


def provide_list_member_options(session: SessionDependency) -> ListMemberOptions:
    return wiring.build_list_member_options(session)


def provide_get_member(session: SessionDependency) -> GetMember:
    return wiring.build_get_member(session)


def provide_send_password_link(session: SessionDependency) -> SendPasswordLink:
    return wiring.build_send_password_link(session)


def provide_set_password(session: SessionDependency) -> SetPassword:
    return wiring.build_set_password(session)
