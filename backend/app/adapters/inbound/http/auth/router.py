from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.adapters.inbound.http.auth.dependencies import (
    get_current_user,
    provide_login,
    provide_logout,
    provide_refresh_access,
)
from app.adapters.inbound.http.auth.schemas import Token, UserCredentials
from app.adapters.inbound.http.users.schemas import UserPublic
from app.bootstrap.settings import settings
from app.core.auth.application.commands import Login, Logout, RefreshAccess
from app.core.auth.application.dto import LoginCommand, LogoutCommand, RefreshCommand
from app.core.auth.domain.session import AuthenticationError
from app.core.users.public import UserDetails

router = APIRouter(prefix="/api/auth", tags=["auth"])


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=int(timedelta(days=settings.refresh_token_expire_days).total_seconds()),
        path=settings.cookie_path,
    )


@router.post("/login", response_model=Token)
def login(
    credentials: UserCredentials,
    response: Response,
    use_case: Annotated[Login, Depends(provide_login)],
):
    try:
        result = use_case.execute(
            LoginCommand(email=credentials.email, password=credentials.password)
        )
    except AuthenticationError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    set_refresh_cookie(response, result.refresh_token)
    return Token(access_token=result.access_token, token_type="bearer")


@router.post("/refresh", response_model=Token)
def refresh(
    request: Request,
    response: Response,
    use_case: Annotated[RefreshAccess, Depends(provide_refresh_access)],
):
    token = request.cookies.get(settings.refresh_cookie_name)
    if token is None:
        raise HTTPException(status_code=401, detail="Keine Refresh-Session vorhanden")
    try:
        result = use_case.execute(RefreshCommand(refresh_token=token))
    except AuthenticationError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    set_refresh_cookie(response, result.refresh_token)
    return Token(access_token=result.access_token, token_type="bearer")


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    use_case: Annotated[Logout, Depends(provide_logout)],
):
    use_case.execute(
        LogoutCommand(refresh_token=request.cookies.get(settings.refresh_cookie_name))
    )
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path=settings.cookie_path,
        secure=settings.cookie_secure,
        httponly=True,
        samesite=settings.cookie_samesite,
    )


@router.get("/me", response_model=UserPublic)
def get_me(current_user: Annotated[UserDetails, Depends(get_current_user)]):
    return current_user
