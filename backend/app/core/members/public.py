"""Public member contracts for account administration and player images."""

from typing import Protocol

from app.core.members.domain.member import Member
from app.core.members.application.dto import GetPlayerImagesQuery
from app.core.members.application.queries import GetPlayerImages
from app.core.members.application.commands import AssignPlayerImage
from app.core.members.application.dto import AssignPlayerImageCommand
from app.core.members.application.errors import (
    PlayerImageAssignmentNotFound, PlayerImageForbidden, PlayerImageMediaNotFound,
)


class Members(Protocol):
    def get(self, member_id: int) -> Member | None: ...
    def save(self, member: Member) -> Member: ...


__all__ = [
    "Member", "Members", "GetPlayerImages", "GetPlayerImagesQuery",
    "AssignPlayerImage", "AssignPlayerImageCommand", "PlayerImageAssignmentNotFound",
    "PlayerImageForbidden", "PlayerImageMediaNotFound",
]
