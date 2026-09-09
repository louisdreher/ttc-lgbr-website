from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum


class RoleName(StrEnum):
    ADMIN = "ADMIN"
    EDITOR = "EDITOR"
    TEAM_REPORTER = "TEAM_REPORTER"


def normalize_email(email: str) -> str:
    return email.strip().lower()


@dataclass(frozen=True)
class Role:
    id: int
    name: str


@dataclass(kw_only=True)
class User:
    email: str
    name: str
    password_hash: str = field(repr=False)
    id: int | None = None
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    member_id: int | None = None
    roles: list[Role] = field(default_factory=list)

    @classmethod
    def create(cls, *, email: str, name: str, password_hash: str) -> "User":
        return cls(
            email=normalize_email(email), name=name.strip(), password_hash=password_hash
        )

    def add_role(self, role: Role) -> None:
        if not any(existing.id == role.id for existing in self.roles):
            self.roles.append(role)

    def remove_role(self, role: Role) -> None:
        self.roles = [existing for existing in self.roles if existing.id != role.id]
