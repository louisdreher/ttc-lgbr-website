from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from app.adapters.outbound.persistence.database import get_session
from app.bootstrap import users as wiring
from app.core.users.application.commands import AddUserRole, CreateUser, RemoveUserRole


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
