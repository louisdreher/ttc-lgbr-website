from dataclasses import dataclass, field


@dataclass(frozen=True, kw_only=True)
class LoginCommand:
    email: str
    password: str = field(repr=False)


@dataclass(frozen=True, kw_only=True)
class RefreshCommand:
    refresh_token: str = field(repr=False)


@dataclass(frozen=True, kw_only=True)
class LogoutCommand:
    refresh_token: str | None = field(repr=False)


@dataclass(frozen=True, kw_only=True)
class CurrentUserQuery:
    access_token: str = field(repr=False)


@dataclass(frozen=True, kw_only=True)
class IssuedTokens:
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
