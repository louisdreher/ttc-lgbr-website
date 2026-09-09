from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


class AuthenticationError(ValueError):
    pass


class SessionReusedError(AuthenticationError):
    pass


@dataclass(kw_only=True)
class RefreshSession:
    user_id: int
    token_hash: str = field(repr=False)
    expires_at: datetime
    id: UUID = field(default_factory=uuid4)
    family_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    used_at: datetime | None = None
    revoked_at: datetime | None = None

    def use(self, now: datetime) -> None:
        if self.revoked_at is not None:
            raise AuthenticationError("Session wurde widerrufen")
        if self.expires_at <= now:
            raise AuthenticationError("Session ist abgelaufen")
        if self.used_at is not None:
            raise SessionReusedError("Refresh Token wurde bereits verwendet")
        self.used_at = now
