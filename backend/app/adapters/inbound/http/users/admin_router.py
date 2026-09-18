from contextlib import contextmanager
from typing import Annotated

from app.adapters.inbound.http.auth.permissions import require_role
from app.adapters.inbound.http.users import dependencies as deps
from app.adapters.inbound.http.users.admin_schemas import (
    ActiveWrite,
    CreatedUser,
    ManagedUserPublic,
    ManagedUserWrite,
    MemberOptionPublic,
    MemberPublic,
    PasswordWrite,
    UserPagePublic,
)
from app.core.members.public import Member
from app.core.users.application.commands import (
    DeleteUser,
    SaveManagedUser,
    SendPasswordLink,
    SetPassword,
    SetUserActive,
)
from app.core.users.application.dto import ListUsersQuery, SaveManagedUserCommand
from app.core.users.application.errors import (
    InvalidPasswordLinkError,
    MailDeliveryError,
    RoleNotFoundError,
    UserAlreadyExistsError,
    UserConflictError,
    UserNotFoundError,
)
from app.core.users.application.queries import (
    GetManagedUser,
    GetMember,
    ListMemberOptions,
    ListUsers,
)
from app.core.users.domain.user import RoleName
from fastapi import APIRouter, Depends, HTTPException, Query, Response

router = APIRouter(
    prefix="/api/admin/users",
    tags=["Benutzerverwaltung"],
    dependencies=[Depends(require_role(RoleName.ADMIN))],
)
password_router = APIRouter(prefix="/api/auth", tags=["auth"])


@contextmanager
def user_errors():
    try:
        yield
    except (UserNotFoundError, RoleNotFoundError) as error:
        raise HTTPException(404, str(error)) from error
    except (UserAlreadyExistsError, UserConflictError) as error:
        raise HTTPException(409, str(error)) from error
    except MailDeliveryError as error:
        raise HTTPException(503, str(error)) from error
    except (InvalidPasswordLinkError, ValueError) as error:
        raise HTTPException(400, str(error)) from error


@router.get("", response_model=UserPagePublic)
def list_users(
    use_case: Annotated[ListUsers, Depends(deps.provide_list_users)],
    search: str = Query(default="", max_length=200),
    role: RoleName | None = None,
    active: bool | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
):
    return use_case.execute(ListUsersQuery(search, role, active, offset, limit))


@router.get("/members", response_model=list[MemberOptionPublic])
def member_options(
    use_case: Annotated[ListMemberOptions, Depends(deps.provide_list_member_options)],
):
    return use_case.execute()


@router.get("/members/{member_id}", response_model=MemberPublic)
def get_member(
    member_id: int, use_case: Annotated[GetMember, Depends(deps.provide_get_member)]
):
    with user_errors():
        return use_case.execute(member_id)


@router.get("/{user_id}", response_model=ManagedUserPublic)
def get_user(
    user_id: int,
    use_case: Annotated[GetManagedUser, Depends(deps.provide_get_managed_user)],
):
    with user_errors():
        return use_case.execute(user_id)


def save_command(data: ManagedUserWrite, user_id: int | None = None):
    return SaveManagedUserCommand(
        user_id=user_id,
        **data.model_dump(exclude={"member"}),
        member=Member(**data.member.model_dump()) if data.member else None,
    )


@router.post("", response_model=CreatedUser, status_code=201)
def create_user(
    data: ManagedUserWrite,
    use_case: Annotated[SaveManagedUser, Depends(deps.provide_save_managed_user)],
):
    with user_errors():
        return {"id": use_case.execute(save_command(data))}


@router.put("/{user_id}", status_code=204)
def update_user(
    user_id: int,
    data: ManagedUserWrite,
    use_case: Annotated[SaveManagedUser, Depends(deps.provide_save_managed_user)],
):
    with user_errors():
        use_case.execute(save_command(data, user_id))


@router.patch("/{user_id}/active", status_code=204)
def set_active(
    user_id: int,
    data: ActiveWrite,
    use_case: Annotated[SetUserActive, Depends(deps.provide_set_user_active)],
):
    with user_errors():
        use_case.execute(user_id, data.is_active)


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: int, use_case: Annotated[DeleteUser, Depends(deps.provide_delete_user)]
):
    with user_errors():
        use_case.execute(user_id)


@router.post("/{user_id}/password-link", status_code=204)
def send_password_link(
    user_id: int,
    use_case: Annotated[SendPasswordLink, Depends(deps.provide_send_password_link)],
):
    with user_errors():
        use_case.execute(user_id)


@password_router.post("/set-password", status_code=204)
def set_password(
    data: PasswordWrite,
    response: Response,
    use_case: Annotated[SetPassword, Depends(deps.provide_set_password)],
):
    response.headers["Cache-Control"] = "no-store"
    with user_errors():
        use_case.execute(data.token, data.password)
