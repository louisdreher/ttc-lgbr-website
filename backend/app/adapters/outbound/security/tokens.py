import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt


class JwtTokens:
    def __init__(self, *, secret: str, algorithm: str, access_lifetime: timedelta):
        self.secret = secret
        self.algorithm = algorithm
        self.access_lifetime = access_lifetime

    def issue_access(self, user_id: int, now: datetime) -> str:
        return jwt.encode(
            {
                "sub": str(user_id),
                "exp": now + self.access_lifetime,
                "iat": now.timestamp(),
            },
            self.secret,
            algorithm=self.algorithm,
        )

    def decode_access(self, token: str) -> int | None:
        try:
            payload = jwt.decode(
                token,
                self.secret,
                algorithms=[self.algorithm],
                options={"require": ["sub", "exp"]},
            )
            return int(payload["sub"])
        except (jwt.InvalidTokenError, ValueError, TypeError):
            return None

    def new_refresh(self) -> str:
        return secrets.token_urlsafe(32)

    def issued_after(self, token: str, cutoff: datetime) -> bool:
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
            cutoff = (
                cutoff.replace(tzinfo=timezone.utc) if cutoff.tzinfo is None else cutoff
            )
            return float(payload.get("iat", 0)) > cutoff.timestamp()
        except (jwt.InvalidTokenError, ValueError, TypeError):
            return False

    def hash_refresh(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
