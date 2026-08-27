from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.core.settings import settings
from app.domains.users.model import User
from app.domains.users.service import get_user_by_email
from fastapi import HTTPException, status
from sqlmodel import Session

from .model import RefreshSession
from .schemas import UserCredentials
from .security import create_refresh_token, hash_refresh_token, verify_password


def authenticate_user(session: Session, credentials: UserCredentials):
    user: User = get_user_by_email(session, credentials.email)
    if user is None:
        return
    if not verify_password(credentials.password, user.password_hash):
        return None
    if not user.is_active:
        return None
    return user


def create_refresh_session(
    session: Session, user_id: int
) -> tuple[str, RefreshSession]:

    refresh_token = create_refresh_token()

    token_hash = hash_refresh_token(refresh_token)

    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )

    refresh_session = RefreshSession(
        user_id=user_id, token_hash=token_hash, expires_at=expires_at
    )

    session.add(refresh_session)
    session.commit()
    session.refresh(refresh_session)

    return refresh_token, refresh_session


from sqlmodel import Session, select


def get_refresh_session(session: Session, refresh_token: str) -> RefreshSession | None:

    token_hash = hash_refresh_token(refresh_token)

    statement = select(RefreshSession).where(RefreshSession.token_hash == token_hash)

    return session.exec(statement).first()


def revoke_refresh_family(session: Session, family_id: UUID) -> None:

    now = datetime.now(timezone.utc)

    statement = select(RefreshSession).where(
        RefreshSession.family_id == family_id, RefreshSession.revoked_at == None
    )

    refresh_sessions = session.exec(statement).all()

    for refresh_session in refresh_sessions:
        refresh_session.revoked_at = now
        session.add(refresh_session)

    session.commit()


def rotate_refresh_token(
    session: Session, refresh_token: str
) -> tuple[str, RefreshSession]:

    refresh_session = get_refresh_session(session=session, refresh_token=refresh_token)

    # 1. Token unbekannt
    if refresh_session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Ungültige Session"
        )

    now = datetime.now(timezone.utc)

    # 2. Token / Session wurde bereits widerrufen
    if refresh_session.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session wurde widerrufen"
        )

    # 3. Token ist abgelaufen
    if refresh_session.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session ist abgelaufen"
        )

    # 4. Token wurde schon einmal benutzt → Replay
    if refresh_session.used_at is not None:
        revoke_refresh_family(session=session, family_id=refresh_session.family_id)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh Token wurde bereits verwendet",
        )

    # 5. Alten Token als benutzt markieren
    refresh_session.used_at = now
    session.add(refresh_session)

    # 6. Neuen Refresh Token erzeugen
    new_refresh_token = create_refresh_token()
    new_token_hash = hash_refresh_token(new_refresh_token)

    new_refresh_session = RefreshSession(
        user_id=refresh_session.user_id,
        token_hash=new_token_hash,
        family_id=refresh_session.family_id,
        expires_at=now + timedelta(days=settings.refresh_token_expire_days),
    )

    session.add(new_refresh_session)

    # Beide Änderungen gemeinsam speichern
    session.commit()
    session.refresh(new_refresh_session)

    return new_refresh_token, new_refresh_session


def logout_refresh_session(session: Session, refresh_token: str) -> None:

    refresh_session = get_refresh_session(session=session, refresh_token=refresh_token)

    if refresh_session is None:
        return

    revoke_refresh_family(session=session, family_id=refresh_session.family_id)
