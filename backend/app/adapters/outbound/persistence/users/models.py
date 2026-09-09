from datetime import datetime, timezone

from sqlmodel import Field, Relationship, SQLModel


class UserRoleLink(SQLModel, table=True):
    user_id: int = Field(foreign_key="user.id", primary_key=True)

    role_id: int = Field(foreign_key="role.id", primary_key=True)


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    email: str = Field(index=True, unique=True)
    name: str

    password_hash: str

    is_active: bool = True

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    member_id: int | None = Field(
        default=None,
        foreign_key="member.id",
        unique=True,
    )

    roles: list["Role"] = Relationship(back_populates="users", link_model=UserRoleLink)


class Role(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    name: str = Field(unique=True, index=True)

    users: list["User"] = Relationship(back_populates="roles", link_model=UserRoleLink)
