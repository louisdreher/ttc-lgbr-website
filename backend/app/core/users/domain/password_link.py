from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(kw_only=True)
class PasswordLink:
    user_id: int
    token_hash: str = field(repr=False)
    expires_at: datetime

    def valid_at(self, now: datetime) -> bool:
        expiry = (
            self.expires_at.replace(tzinfo=timezone.utc)
            if self.expires_at.tzinfo is None
            else self.expires_at
        )
        return now < expiry
