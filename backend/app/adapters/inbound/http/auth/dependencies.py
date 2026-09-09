from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from app.adapters.outbound.persistence.database import get_session
from app.bootstrap import auth as wiring
from app.core.auth.application.commands import Login, Logout, RefreshAccess
from app.core.auth.application.dto import CurrentUserQuery
from app.core.auth.application.queries import GetCurrentUser
from app.core.auth.domain.session import AuthenticationError
from app.core.users.public import UserDetails

bearer_scheme = HTTPBearer(auto_error=False)


def provide_login(session: Annotated[Session, Depends(get_session)]) -> Login:
    return wiring.build_login(session)


def provide_refresh_access(
    session: Annotated[Session, Depends(get_session)],
) -> RefreshAccess:
    return wiring.build_refresh_access(session)


def provide_logout(session: Annotated[Session, Depends(get_session)]) -> Logout:
    return wiring.build_logout(session)


def provide_current_user(
    session: Annotated[Session, Depends(get_session)],
) -> GetCurrentUser:
    return wiring.build_get_current_user(session)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    use_case: Annotated[GetCurrentUser, Depends(provide_current_user)],
) -> UserDetails:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Nicht authentifiziert",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return use_case.execute(CurrentUserQuery(access_token=credentials.credentials))
    except AuthenticationError as error:
        raise HTTPException(
            status_code=401, detail=str(error), headers={"WWW-Authenticate": "Bearer"}
        ) from error
