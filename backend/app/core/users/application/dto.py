from dataclasses import dataclass, field

from app.core.users.domain.user import RoleName, User


@dataclass(frozen=True, kw_only=True)
class CreateUserCommand:
    email: str
    name: str
    password: str = field(repr=False)


@dataclass(frozen=True, kw_only=True)
class ChangeUserRoleCommand:
    user_id: int
    role_name: RoleName


@dataclass(frozen=True, kw_only=True)
class UserDetails:
    """Public user projection: deliberately contains no credential material."""

    id: int
    email: str
    name: str
    is_active: bool
    roles: list[str]
    is_system: bool = False

    @classmethod
    def from_user(cls, user: User) -> "UserDetails":
        if user.id is None:
            raise RuntimeError("Der gespeicherte Benutzer besitzt keine ID.")
        return cls(
            id=user.id,
            email=user.email,
            name=user.name,
            is_active=user.is_active,
            roles=[role.name for role in user.roles],
            is_system=user.system_key is not None,
        )


@dataclass(frozen=True, kw_only=True)
class UserCredentials:
    """Internal authentication contract; never a response DTO."""

    user_id: int
    is_active: bool
    password_hash: str = field(repr=False)
    is_system: bool = False
