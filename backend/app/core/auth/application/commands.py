from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from app.core.auth.application.dto import (
    IssuedTokens,
    LoginCommand,
    LogoutCommand,
    RefreshCommand,
)
from app.core.auth.application.ports import AuthUnitOfWork, Tokens
from app.core.auth.domain.session import (
    AuthenticationError,
    RefreshSession,
    SessionReusedError,
)
from app.core.users.public import Passwords, UserReader


class Login:
    def __init__(
        self,
        uow: AuthUnitOfWork,
        users: UserReader,
        passwords: Passwords,
        tokens: Tokens,
        refresh_lifetime: timedelta,
        clock: Callable[[], datetime],
    ):
        self.uow = uow
        self.users = users
        self.passwords = passwords
        self.tokens = tokens
        self.refresh_lifetime = refresh_lifetime
        self.clock = clock

    def execute(self, command: LoginCommand) -> IssuedTokens:
        with self.uow:
            # A reset racing password verification must invalidate this login too.
            now = self.clock()
            user = self.users.get_credentials(command.email)
            if (
                user is None
                or not user.is_active
                or user.is_system
                or not self.passwords.verify(command.password, user.password_hash)
            ):
                raise AuthenticationError("E-Mail oder Passwort ist falsch")
            refresh_token = self.tokens.new_refresh()
            session = RefreshSession(
                user_id=user.user_id,
                token_hash=self.tokens.hash_refresh(refresh_token),
                created_at=now,
                expires_at=now + self.refresh_lifetime,
            )
            self.uow.sessions.save(session)
            result = IssuedTokens(
                access_token=self.tokens.issue_access(user.user_id, now),
                refresh_token=refresh_token,
            )
            self.uow.commit()
            return result


class RefreshAccess:
    def __init__(
        self,
        uow: AuthUnitOfWork,
        users: UserReader,
        tokens: Tokens,
        refresh_lifetime: timedelta,
        clock: Callable[[], datetime],
    ):
        self.uow = uow
        self.users = users
        self.tokens = tokens
        self.refresh_lifetime = refresh_lifetime
        self.clock = clock

    def execute(self, command: RefreshCommand) -> IssuedTokens:
        reuse_error = None
        with self.uow:
            session = self.uow.sessions.get_for_update(
                self.tokens.hash_refresh(command.refresh_token)
            )
            if session is None:
                raise AuthenticationError("Ungültige Session")
            now = self.clock()
            try:
                session.use(now)
            except SessionReusedError as error:
                # Commit the revocation before reporting the rejected request.
                self.uow.sessions.revoke_family(session.family_id, now)
                self.uow.commit()
                reuse_error = error
            if reuse_error is None:
                user = self.users.get_public(session.user_id)
                if user is None or not user.is_active or user.is_system:
                    raise AuthenticationError(
                        "Benutzer ist deaktiviert oder nicht vorhanden"
                    )
                if user.auth_invalid_before:
                    cutoff = (
                        user.auth_invalid_before.replace(tzinfo=timezone.utc)
                        if user.auth_invalid_before.tzinfo is None
                        else user.auth_invalid_before
                    )
                    created = (
                        session.created_at.replace(tzinfo=timezone.utc)
                        if session.created_at.tzinfo is None
                        else session.created_at
                    )
                    if created <= cutoff:
                        raise AuthenticationError("Bitte erneut anmelden.")
                refresh_token = self.tokens.new_refresh()
                self.uow.sessions.save(session)
                self.uow.sessions.save(
                    RefreshSession(
                        user_id=session.user_id,
                        family_id=session.family_id,
                        token_hash=self.tokens.hash_refresh(refresh_token),
                        created_at=now,
                        expires_at=now + self.refresh_lifetime,
                    )
                )
                result = IssuedTokens(
                    access_token=self.tokens.issue_access(session.user_id, now),
                    refresh_token=refresh_token,
                )
                self.uow.commit()
                return result
        # Raising outside the UoW prevents a rollback of the intended revocation.
        raise reuse_error


class Logout:
    def __init__(
        self, uow: AuthUnitOfWork, tokens: Tokens, clock: Callable[[], datetime]
    ):
        self.uow = uow
        self.tokens = tokens
        self.clock = clock

    def execute(self, command: LogoutCommand) -> None:
        if command.refresh_token is None:
            return
        with self.uow:
            session = self.uow.sessions.get_for_update(
                self.tokens.hash_refresh(command.refresh_token)
            )
            if session is not None:
                self.uow.sessions.revoke_family(session.family_id, self.clock())
                self.uow.commit()
