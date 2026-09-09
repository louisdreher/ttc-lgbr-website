from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.adapters.inbound.http.auth.permissions import require_role
from app.adapters.inbound.http.users.dependencies import (
    provide_add_user_role,
    provide_create_user,
    provide_remove_user_role,
)
from app.adapters.inbound.http.users.schemas import UserCreate, UserPublic
from app.core.users.application.commands import AddUserRole, CreateUser, RemoveUserRole
from app.core.users.application.dto import ChangeUserRoleCommand, CreateUserCommand
from app.core.users.application.errors import (
    RoleNotFoundError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from app.core.users.public import RoleName, UserDetails

router = APIRouter(prefix="/api/users", tags=["Users"])
user_admin = require_role(RoleName.ADMIN)


@router.post("/", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def create_user_endpoint(
    user_data: UserCreate,
    admin_user: Annotated[UserDetails, Depends(user_admin)],
    use_case: Annotated[CreateUser, Depends(provide_create_user)],
):
    try:
        return use_case.execute(CreateUserCommand(**user_data.model_dump()))
    except UserAlreadyExistsError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.put("/{user_id}/roles/{role_name}")
def add_role(
    user_id: int,
    role_name: RoleName,
    admin_user: Annotated[UserDetails, Depends(user_admin)],
    use_case: Annotated[AddUserRole, Depends(provide_add_user_role)],
):
    try:
        use_case.execute(ChangeUserRoleCommand(user_id=user_id, role_name=role_name))
    except (UserNotFoundError, RoleNotFoundError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"message": f"Rolle {role_name.value} wurde dem User zugewiesen."}


@router.delete("/{user_id}/roles/{role_name}")
def remove_role(
    user_id: int,
    role_name: RoleName,
    admin_user: Annotated[UserDetails, Depends(user_admin)],
    use_case: Annotated[RemoveUserRole, Depends(provide_remove_user_role)],
):
    try:
        use_case.execute(ChangeUserRoleCommand(user_id=user_id, role_name=role_name))
    except (UserNotFoundError, RoleNotFoundError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"message": f"Rolle {role_name.value} wurde vom User entfernt."}
