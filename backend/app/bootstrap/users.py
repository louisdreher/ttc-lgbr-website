from datetime import datetime, timedelta, timezone

from app.adapters.outbound.mail.password_mail import SmtpPasswordMail
from app.adapters.outbound.persistence.users.administration_reader import (
    SqlUserAdministrationReader,
)
from app.adapters.outbound.persistence.users.unit_of_work import SqlUserUnitOfWork
from app.adapters.outbound.security.password_links import SecurePasswordLinkTokens
from app.adapters.outbound.security.passwords import ArgonPasswords
from app.bootstrap.settings import settings
from app.core.users.application.commands import (
    AddUserRole,
    CreateUser,
    CreateFirstAdmin,
    DeleteUser,
    EnsureDefaultRoles,
    RemoveUserRole,
    SaveManagedUser,
    SendPasswordLink,
    SetPassword,
    SetUserActive,
)
from app.core.users.application.queries import (
    GetManagedUser,
    GetMember,
    ListMemberOptions,
    ListUsers,
)
from sqlmodel import Session


def build_create_first_admin(session: Session) -> CreateFirstAdmin:
    return CreateFirstAdmin(SqlUserUnitOfWork(session), ArgonPasswords())


def build_create_user(session: Session) -> CreateUser:
    return CreateUser(SqlUserUnitOfWork(session), ArgonPasswords())


def build_add_user_role(session: Session) -> AddUserRole:
    return AddUserRole(SqlUserUnitOfWork(session))


def build_remove_user_role(session: Session) -> RemoveUserRole:
    return RemoveUserRole(SqlUserUnitOfWork(session))


def build_ensure_default_roles(session: Session) -> EnsureDefaultRoles:
    return EnsureDefaultRoles(SqlUserUnitOfWork(session))


def utc_now():
    return datetime.now(timezone.utc)


def build_save_managed_user(session: Session) -> SaveManagedUser:
    return SaveManagedUser(SqlUserUnitOfWork(session), utc_now)


def build_set_user_active(session: Session) -> SetUserActive:
    return SetUserActive(SqlUserUnitOfWork(session), utc_now)


def build_delete_user(session: Session) -> DeleteUser:
    return DeleteUser(SqlUserUnitOfWork(session))


def build_list_users(session: Session) -> ListUsers:
    return ListUsers(SqlUserAdministrationReader(session))


def build_get_managed_user(session: Session) -> GetManagedUser:
    return GetManagedUser(SqlUserAdministrationReader(session))


def build_list_member_options(session: Session) -> ListMemberOptions:
    return ListMemberOptions(SqlUserAdministrationReader(session))


def build_get_member(session: Session) -> GetMember:
    return GetMember(SqlUserAdministrationReader(session))


def build_send_password_link(session: Session) -> SendPasswordLink:
    mail = SmtpPasswordMail(
        host=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username,
        password=settings.smtp_password,
        sender=settings.smtp_sender,
        starttls=settings.smtp_starttls,
        public_url=settings.public_frontend_url,
        lifetime_minutes=settings.password_link_minutes,
    )
    return SendPasswordLink(
        SqlUserUnitOfWork(session),
        SecurePasswordLinkTokens(),
        mail,
        utc_now,
        timedelta(minutes=settings.password_link_minutes),
    )


def build_set_password(session: Session) -> SetPassword:
    return SetPassword(
        SqlUserUnitOfWork(session),
        SecurePasswordLinkTokens(),
        ArgonPasswords(),
        utc_now,
    )
