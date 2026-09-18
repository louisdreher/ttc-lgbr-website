from app.adapters.outbound.persistence.members.models import Member
from app.adapters.outbound.persistence.members.repository import to_member
from app.adapters.outbound.persistence.users.models import Role, User
from app.core.users.application.dto import (
    ListUsersQuery,
    ManagedUser,
    MemberOption,
    UserPage,
)
from sqlalchemy import func, or_
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select


class SqlUserAdministrationReader:
    def __init__(self, session: Session):
        self.session = session

    def project(self, user: User, member: Member | None) -> ManagedUser:
        return ManagedUser(
            id=user.id,
            name=user.name,
            email=user.email,
            is_active=user.is_active,
            created_at=user.created_at,
            roles=sorted(r.name for r in user.roles),
            member_id=user.member_id,
            member=to_member(member) if member else None,
        )

    def list_users(self, query: ListUsersQuery) -> UserPage:
        conditions = [User.system_key.is_(None)]
        if query.search.strip():
            term = (
                query.search.strip()
                .replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            conditions.append(
                or_(
                    User.name.ilike(f"%{term}%", escape="\\"),
                    User.email.ilike(f"%{term}%", escape="\\"),
                )
            )
        if query.role:
            conditions.append(User.roles.any(Role.name == query.role.value))
        if query.active is not None:
            conditions.append(User.is_active == query.active)
        total = self.session.exec(
            select(func.count()).select_from(User).where(*conditions)
        ).one()
        rows = self.session.exec(
            select(User, Member)
            .outerjoin(Member, User.member_id == Member.id)
            .options(selectinload(User.roles))
            .where(*conditions)
            .order_by(func.lower(User.name), User.id)
            .offset(query.offset)
            .limit(query.limit)
        ).all()
        return UserPage(
            items=[self.project(user, member) for user, member in rows], total=total
        )

    def get_user(self, user_id: int) -> ManagedUser | None:
        row = self.session.exec(
            select(User, Member)
            .outerjoin(Member, User.member_id == Member.id)
            .where(User.id == user_id, User.system_key.is_(None))
        ).first()
        return self.project(*row) if row else None

    def member_options(self) -> list[MemberOption]:
        rows = self.session.exec(
            select(Member.id, Member.first_name, Member.last_name, User.id)
            .outerjoin(User, User.member_id == Member.id)
            .order_by(Member.last_name, Member.first_name, Member.id)
        ).all()
        return [
            MemberOption(id=mid, first_name=first, last_name=last, user_id=uid)
            for mid, first, last, uid in rows
        ]

    def get_member(self, member_id: int):
        row = self.session.get(Member, member_id)
        return to_member(row) if row else None
