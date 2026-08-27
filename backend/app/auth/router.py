from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlmodel import Session

from backend.app.core.database import get_session
from backend.app.core.settings import settings
from backend.app.domains.users.model import User
from backend.app.domains.users.schemas import UserPublic

from .dependencies import get_current_user
from .schemas import Token, UserCredentials
from .security import create_access_token
from .services import (
    authenticate_user,
    create_refresh_session,
    logout_refresh_session,
    rotate_refresh_token,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def set_refresh_cookie(
    response: Response,
    refresh_token: str,
) -> None:
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
    session: Session = Depends(get_session),
):

    user = authenticate_user(session, credentials)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-Mail oder Passwort ist falsch",
        )

    assert user.id is not None

    # Kurzlebiger Access Token
    access_token = create_access_token(user_id=user.id)

    # Langlebiger Refresh Token + DB-Session
    refresh_token, _ = create_refresh_session(session=session, user_id=user.id)

    set_refresh_cookie(response, refresh_token)

    return Token(access_token=access_token, token_type="bearer")


@router.post("/refresh", response_model=Token)
def refresh(
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
):
    # 1. Refresh Token aus dem HttpOnly-Cookie lesen
    refresh_token = request.cookies.get(settings.refresh_cookie_name)

    if refresh_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Keine Refresh-Session vorhanden",
        )

    # 2. Alten Refresh Token prüfen und rotieren
    new_refresh_token, refresh_session = rotate_refresh_token(
        session=session,
        refresh_token=refresh_token,
    )

    # 3. Neuen kurzlebigen Access Token erstellen
    access_token = create_access_token(user_id=refresh_session.user_id)

    # 4. Neuen Refresh Token als HttpOnly-Cookie setzen
    set_refresh_cookie(response, new_refresh_token)

    # 5. Neuen Access Token zurückgeben
    return Token(
        access_token=access_token,
        token_type="bearer",
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request, response: Response, session: Session = Depends(get_session)
):
    refresh_token = request.cookies.get(settings.refresh_cookie_name)

    if refresh_token is not None:
        logout_refresh_session(session=session, refresh_token=refresh_token)

    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path=settings.cookie_path,
        secure=settings.cookie_secure,
        httponly=True,
        samesite=settings.cookie_samesite,
    )


@router.get("/me", response_model=UserPublic)
def get_me(current_user: User = Depends(get_current_user)):
    return UserPublic(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        is_active=current_user.is_active,
        roles=[role.name for role in current_user.roles],
    )
