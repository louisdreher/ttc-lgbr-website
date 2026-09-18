from dataclasses import dataclass
from datetime import date


@dataclass(kw_only=True)
class Member:
    first_name: str
    last_name: str
    id: int | None = None
    birth_date: date | None = None
    joined_at: date | None = None
    eligible_since: date | None = None
    ttc_eligible_since: date | None = None
    is_active: bool = True
    membership_end_date: date | None = None
    phone: str | None = None
    mobile: str | None = None
    email: str | None = None
    street: str | None = None
    house_number: str | None = None
    postal_code: str | None = None
    city: str | None = None
