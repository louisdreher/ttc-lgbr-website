from dataclasses import asdict

from app.adapters.outbound.persistence.members.models import Member as MemberRow
from app.core.members.public import Member
from sqlmodel import Session


def to_member(row: MemberRow) -> Member:
    return Member(**row.model_dump())


class SqlMembers:
    def __init__(self, session: Session):
        self.session = session

    def get(self, member_id: int) -> Member | None:
        row = self.session.get(MemberRow, member_id)
        return to_member(row) if row else None

    def save(self, member: Member) -> Member:
        row = self.session.get(MemberRow, member.id) if member.id else None
        if row is None:
            row = MemberRow(**asdict(member))
        else:
            row.sqlmodel_update(asdict(member))
        self.session.add(row)
        self.session.flush()
        member.id = row.id
        return member
