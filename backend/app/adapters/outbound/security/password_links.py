import hashlib
import secrets


class SecurePasswordLinkTokens:
    def create(self) -> str:
        return secrets.token_urlsafe(32)

    def digest(self, token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()
