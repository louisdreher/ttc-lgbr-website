"""Member data contract used by account administration in a shared transaction."""

from typing import Protocol

from app.core.members.domain.member import Member


class Members(Protocol):
    def get(self, member_id: int) -> Member | None: ...
    def save(self, member: Member) -> Member: ...


__all__ = ["Member", "Members"]
