from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timedelta

from app.core.users.application.dto import (
    ChangeUserRoleCommand,
    CreateUserCommand,
    SaveManagedUserCommand,
    UserDetails,
)
from app.core.users.application.errors import (
    InvalidPasswordLinkError,
    RoleNotFoundError,
    UserAlreadyExistsError,
    UserConflictError,
    UserNotFoundError,
)
from app.core.users.application.ports import (
    PasswordLinkTokens,
    PasswordMail,
    Passwords,
    UserUnitOfWork,
)
from app.core.users.domain.password_link import PasswordLink
from app.core.users.domain.user import Role, RoleName, User, normalize_email


class CreateFirstAdmin:
    """Explicit first-time setup; never promotes or resets an existing account."""

    def __init__(self, uow: UserUnitOfWork, passwords: Passwords):
        self.uow, self.passwords = uow, passwords

    def execute(self, command: CreateUserCommand) -> UserDetails:
        if not command.name.strip():
            raise ValueError("Name darf nicht leer sein.")
        if not 12 <= len(command.password) <= 128:
            raise ValueError("Das Passwort muss 12 bis 128 Zeichen lang sein.")
        with self.uow:
            self.uow.users.lock_administration()
            role = self.uow.roles.get_by_name(RoleName.ADMIN.value)
            if role is None:
                raise RoleNotFoundError("ADMIN-Rolle fehlt. Bitte zuerst die API starten.")
            if self.uow.users.admin_exists():
                raise UserConflictError("Es existiert bereits ein Administrator, eventuell deaktiviert.")
            if self.uow.users.email_exists(normalize_email(command.email)):
                raise UserAlreadyExistsError("Ein Konto mit dieser E-Mail existiert bereits.")
            user = User.create(
                email=command.email, name=command.name,
                password_hash=self.passwords.hash(command.password),
            )
            user.add_role(role)
            result = UserDetails.from_user(self.uow.users.save(user))
            self.uow.commit()
            return result


class CreateUser:
    def __init__(self, uow: UserUnitOfWork, passwords: Passwords):
        self.uow = uow
        self.passwords = passwords

    def execute(self, command: CreateUserCommand) -> UserDetails:
        with self.uow:
            if self.uow.users.email_exists(normalize_email(command.email)):
                raise UserAlreadyExistsError(
                    "Ein Benutzer mit dieser E-Mail existiert bereits."
                )
            user = User.create(
                email=command.email,
                name=command.name,
                password_hash=self.passwords.hash(command.password),
            )
            result = UserDetails.from_user(self.uow.users.save(user))
            self.uow.commit()
            return result


def _load_user_and_role(
    uow: UserUnitOfWork, command: ChangeUserRoleCommand
) -> tuple[User, Role]:
    uow.users.lock_administration()
    user = uow.users.get(command.user_id)
    if user is None:
        raise UserNotFoundError("User nicht gefunden")
    user.ensure_manageable()
    role = uow.roles.get_by_name(command.role_name.value)
    if role is None:
        raise RoleNotFoundError("Rolle nicht gefunden")
    return user, role


class AddUserRole:
    def __init__(self, uow: UserUnitOfWork):
        self.uow = uow

    def execute(self, command: ChangeUserRoleCommand) -> None:
        with self.uow:
            user, role = _load_user_and_role(self.uow, command)
            user.add_role(role)
            self.uow.users.save(user)
            self.uow.commit()


class RemoveUserRole:
    def __init__(self, uow: UserUnitOfWork):
        self.uow = uow

    def execute(self, command: ChangeUserRoleCommand) -> None:
        with self.uow:
            user, role = _load_user_and_role(self.uow, command)
            if (
                role.name == RoleName.ADMIN
                and user.is_admin()
                and self.uow.users.active_admin_count() <= 1
            ):
                raise UserConflictError(
                    "Der letzte aktive Administrator muss erhalten bleiben."
                )
            user.remove_role(role)
            self.uow.users.save(user)
            self.uow.commit()


class EnsureDefaultRoles:
    """Preserves the old idempotent helper; does not create an administrator."""

    def __init__(self, uow: UserUnitOfWork):
        self.uow = uow

    def execute(self) -> None:
        with self.uow:
            for role in RoleName:
                if self.uow.roles.get_by_name(role.value) is None:
                    self.uow.roles.add(role.value)
            self.uow.commit()


def managed_user(uow: UserUnitOfWork, user_id: int) -> User:
    user = uow.users.get(user_id)
    if user is None:
        raise UserNotFoundError("Benutzer nicht gefunden.")
    user.ensure_manageable()
    return user


def protect_last_admin(uow: UserUnitOfWork, user: User) -> None:
    if user.is_admin() and uow.users.active_admin_count() <= 1:
        raise UserConflictError(
            "Der letzte aktive Administrator muss erhalten bleiben."
        )


class SaveManagedUser:
    def __init__(self, uow: UserUnitOfWork, clock: Callable[[], datetime]):
        self.uow, self.clock = uow, clock

    def execute(self, command: SaveManagedUserCommand) -> int:
        with self.uow:
            self.uow.users.lock_administration()
            user = (
                managed_user(self.uow, command.user_id)
                if command.user_id is not None
                else User.create(
                    email=command.email, name=command.name, password_hash="!"
                )
            )
            email = normalize_email(command.email)
            if (user.id is None or email != user.email) and self.uow.users.email_exists(
                email
            ):
                raise UserAlreadyExistsError(
                    "Ein Benutzer mit dieser E-Mail existiert bereits."
                )
            if not command.is_active or RoleName.ADMIN not in command.roles:
                protect_last_admin(self.uow, user)
            roles = []
            for name in dict.fromkeys(command.roles):
                role = self.uow.roles.get_by_name(name.value)
                if role is None:
                    raise RoleNotFoundError("Rolle nicht gefunden.")
                roles.append(role)
            member_id = command.member_id
            if member_id is not None:
                if self.uow.members.get(member_id) is None:
                    raise UserNotFoundError("Mitglied nicht gefunden.")
                if self.uow.users.member_in_use(member_id, user.id):
                    raise UserConflictError(
                        "Dieses Mitglied besitzt bereits ein Benutzerkonto."
                    )
            if command.member is not None:
                member_id = self.uow.members.save(
                    replace(command.member, id=member_id)
                ).id
            if user.id and (
                user.email != email or (user.is_active and not command.is_active)
            ):
                user.auth_invalid_before = self.clock()
                self.uow.sessions.revoke(user.id, user.auth_invalid_before)
                self.uow.links.delete_for_user(user.id)
            user.email, user.name = email, command.name.strip()
            user.is_active, user.roles, user.member_id = (
                command.is_active,
                roles,
                member_id,
            )
            saved = self.uow.users.save(user)
            self.uow.commit()
            return saved.id


class SetUserActive:
    def __init__(self, uow: UserUnitOfWork, clock: Callable[[], datetime]):
        self.uow, self.clock = uow, clock

    def execute(self, user_id: int, active: bool) -> None:
        with self.uow:
            self.uow.users.lock_administration()
            user = managed_user(self.uow, user_id)
            if not active:
                protect_last_admin(self.uow, user)
                user.auth_invalid_before = self.clock()
                self.uow.sessions.revoke(user_id, user.auth_invalid_before)
                self.uow.links.delete_for_user(user_id)
            user.is_active = active
            self.uow.users.save(user)
            self.uow.commit()


class DeleteUser:
    def __init__(self, uow: UserUnitOfWork):
        self.uow = uow

    def execute(self, user_id: int) -> None:
        with self.uow:
            self.uow.users.lock_administration()
            user = managed_user(self.uow, user_id)
            protect_last_admin(self.uow, user)
            self.uow.links.delete_for_user(user_id)
            self.uow.sessions.delete(user_id)
            self.uow.users.delete(user)
            self.uow.commit()


class SendPasswordLink:
    def __init__(
        self,
        uow: UserUnitOfWork,
        tokens: PasswordLinkTokens,
        mail: PasswordMail,
        clock: Callable[[], datetime],
        lifetime: timedelta,
    ):
        self.uow, self.tokens, self.mail = uow, tokens, mail
        self.clock, self.lifetime = clock, lifetime

    def execute(self, user_id: int) -> None:
        self.mail.ensure_configured()
        with self.uow:
            self.uow.users.lock_administration()
            user = managed_user(self.uow, user_id)
            if not user.is_active:
                raise UserConflictError("Das Konto muss zuerst aktiviert werden.")
            token = self.tokens.create()
            self.uow.links.replace(
                PasswordLink(
                    user_id=user_id,
                    token_hash=self.tokens.digest(token),
                    expires_at=self.clock() + self.lifetime,
                )
            )
            email = user.email
            self.uow.commit()
        # Delivery failure leaves a valid token; the administrator can retry explicitly.
        self.mail.send(email, token)


class SetPassword:
    def __init__(
        self,
        uow: UserUnitOfWork,
        tokens: PasswordLinkTokens,
        passwords: Passwords,
        clock: Callable[[], datetime],
    ):
        self.uow, self.tokens, self.passwords, self.clock = (
            uow,
            tokens,
            passwords,
            clock,
        )

    def execute(self, token: str, password: str) -> None:
        if not 12 <= len(password) <= 128:
            raise ValueError("Das Passwort muss 12 bis 128 Zeichen enthalten.")
        with self.uow:
            self.uow.users.lock_administration()
            link = self.uow.links.get(self.tokens.digest(token))
            now = self.clock()
            if link is None or not link.valid_at(now):
                raise InvalidPasswordLinkError(
                    "Der Link ist ungültig oder abgelaufen. Bitte einen neuen Link anfordern."
                )
            user = managed_user(self.uow, link.user_id)
            if not user.is_active:
                raise InvalidPasswordLinkError("Der Link ist ungültig oder abgelaufen.")
            user.password_hash = self.passwords.hash(password)
            user.auth_invalid_before = now
            self.uow.users.save(user)
            self.uow.links.delete_for_user(user.id)
            self.uow.sessions.revoke(user.id, now)
            self.uow.commit()
