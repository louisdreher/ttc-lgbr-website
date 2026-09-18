from app.core.members.public import Member
from app.core.users.application.dto import (
    ListUsersQuery,
    ManagedUser,
    MemberOption,
    UserPage,
)
from app.core.users.application.errors import UserNotFoundError
from app.core.users.application.ports import UserAdministrationReader


class ListUsers:
    def __init__(self, reader: UserAdministrationReader):
        self.reader = reader

    def execute(self, query: ListUsersQuery) -> UserPage:
        return self.reader.list_users(query)


class GetManagedUser:
    def __init__(self, reader: UserAdministrationReader):
        self.reader = reader

    def execute(self, user_id: int) -> ManagedUser:
        user = self.reader.get_user(user_id)
        if user is None:
            raise UserNotFoundError("Benutzer nicht gefunden.")
        return user


class ListMemberOptions:
    def __init__(self, reader: UserAdministrationReader):
        self.reader = reader

    def execute(self) -> list[MemberOption]:
        return self.reader.member_options()


class GetMember:
    def __init__(self, reader: UserAdministrationReader):
        self.reader = reader

    def execute(self, member_id: int) -> Member:
        member = self.reader.get_member(member_id)
        if member is None:
            raise UserNotFoundError("Mitglied nicht gefunden.")
        return member
