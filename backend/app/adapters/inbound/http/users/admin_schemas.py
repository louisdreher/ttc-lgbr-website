from datetime import date, datetime, timezone
from typing import Annotated

from app.core.users.domain.user import RoleName
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
OptionalText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]


class MemberWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    first_name: Name
    last_name: Name
    birth_date: date | None = None
    joined_at: date | None = None
    eligible_since: date | None = None
    ttc_eligible_since: date | None = None
    is_active: bool = True
    membership_end_date: date | None = None
    phone: OptionalText | None = None
    mobile: OptionalText | None = None
    email: EmailStr | None = None
    street: OptionalText | None = None
    house_number: OptionalText | None = None
    postal_code: OptionalText | None = None
    city: OptionalText | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.birth_date and self.birth_date > datetime.now(timezone.utc).date():
            raise ValueError("Das Geburtsdatum darf nicht in der Zukunft liegen.")
        if (
            self.joined_at
            and self.membership_end_date
            and self.membership_end_date < self.joined_at
        ):
            raise ValueError("Der Austritt darf nicht vor dem Eintritt liegen.")
        return self


class MemberPublic(MemberWrite):
    id: int


class MemberOptionPublic(BaseModel):
    id: int
    first_name: str
    last_name: str
    user_id: int | None


class ManagedUserWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    email: EmailStr
    name: Name
    roles: list[RoleName] = Field(default_factory=list, max_length=3)
    is_active: bool = True
    member_id: int | None = Field(default=None, gt=0)
    member: MemberWrite | None = None

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class ManagedUserPublic(BaseModel):
    id: int
    name: str
    email: str
    is_active: bool
    roles: list[str]
    created_at: datetime
    member_id: int | None
    member: MemberPublic | None


class UserPagePublic(BaseModel):
    items: list[ManagedUserPublic]
    total: int


class ActiveWrite(BaseModel):
    is_active: bool


class CreatedUser(BaseModel):
    id: int


class PasswordWrite(BaseModel):
    token: str = Field(min_length=32, max_length=200, repr=False)
    password: str = Field(min_length=12, max_length=128, repr=False)
