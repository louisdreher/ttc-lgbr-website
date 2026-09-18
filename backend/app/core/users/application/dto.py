from dataclasses import dataclass, field
from datetime import datetime

from app.core.members.public import Member
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
    auth_invalid_before: datetime | None = None

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
            auth_invalid_before=user.auth_invalid_before,
        )


@dataclass(frozen=True, kw_only=True)
class UserCredentials:
    """Internal authentication contract; never a response DTO."""

    user_id: int
    is_active: bool
    password_hash: str = field(repr=False)
    is_system: bool = False


@dataclass(frozen=True, kw_only=True)
class SaveManagedUserCommand:
    email: str
    name: str
    roles: list[RoleName]
    is_active: bool
    user_id: int | None = None
    member_id: int | None = None
    member: Member | None = None


@dataclass(frozen=True, kw_only=True)
class ManagedUser:
    id: int
    email: str
    name: str
    roles: list[str]
    is_active: bool
    created_at: datetime
    member_id: int | None
    member: Member | None


@dataclass(frozen=True, kw_only=True)
class MemberOption:
    id: int
    first_name: str
    last_name: str
    user_id: int | None


@dataclass(frozen=True)
class UserPage:
    items: list[ManagedUser]
    total: int


@dataclass(frozen=True)
class ListUsersQuery:
    search: str = ""
    role: RoleName | None = None
    active: bool | None = None
    offset: int = 0
    limit: int = 25
