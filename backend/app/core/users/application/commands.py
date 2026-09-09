from app.core.users.application.dto import (
    ChangeUserRoleCommand,
    CreateUserCommand,
    UserDetails,
)
from app.core.users.application.errors import (
    RoleNotFoundError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from app.core.users.application.ports import Passwords, UserUnitOfWork
from app.core.users.domain.user import Role, RoleName, User, normalize_email


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
    user = uow.users.get(command.user_id)
    if user is None:
        raise UserNotFoundError("User nicht gefunden")
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
