from datetime import datetime, timedelta, timezone

from sqlmodel import Session

from app.adapters.outbound.persistence.auth.unit_of_work import SqlAuthUnitOfWork
from app.adapters.outbound.persistence.users.reader import SqlUserReader
from app.adapters.outbound.security.passwords import ArgonPasswords
from app.adapters.outbound.security.tokens import JwtTokens
from app.bootstrap.settings import settings
from app.core.auth.application.commands import Login, Logout, RefreshAccess
from app.core.auth.application.queries import GetCurrentUser


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def build_tokens() -> JwtTokens:
    return JwtTokens(
        secret=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        access_lifetime=timedelta(minutes=settings.access_token_expire_minutes),
    )


def build_login(session: Session) -> Login:
    return Login(
        SqlAuthUnitOfWork(session),
        SqlUserReader(session),
        ArgonPasswords(),
        build_tokens(),
        timedelta(days=settings.refresh_token_expire_days),
        utc_now,
    )


def build_refresh_access(session: Session) -> RefreshAccess:
    return RefreshAccess(
        SqlAuthUnitOfWork(session),
        SqlUserReader(session),
        build_tokens(),
        timedelta(days=settings.refresh_token_expire_days),
        utc_now,
    )


def build_logout(session: Session) -> Logout:
    return Logout(SqlAuthUnitOfWork(session), build_tokens(), utc_now)


def build_get_current_user(session: Session) -> GetCurrentUser:
    return GetCurrentUser(SqlUserReader(session), build_tokens())
