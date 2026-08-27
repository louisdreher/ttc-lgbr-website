from app.auth.permissions import require_role
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from backend.app.core.database import get_session

from .model import RoleName, User
from .schemas import UserCreate, UserPublic
from .service import (
    add_role_to_user,
    create_user,
    get_role_by_name,
    get_user_by_id,
    remove_role_from_user,
)

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.post("/", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def create_user_endpoint(
    user_data: UserCreate,
    session: Session = Depends(get_session),
    admin_user: User = Depends(require_role(RoleName.ADMIN)),
):
    try:
        return create_user(session=session, user_data=user_data)

    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))


@router.put("/{user_id}/roles/{role_name}")
def add_role(
    user_id: int,
    role_name: RoleName,
    session: Session = Depends(get_session),
    admin_user: User = Depends(require_role(RoleName.ADMIN)),
):

    user = get_user_by_id(session=session, user_id=user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User nicht gefunden"
        )

    role = get_role_by_name(session=session, name=role_name.value)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Rolle nicht gefunden"
        )

    add_role_to_user(session=session, user=user, role=role)

    return {"message": f"Rolle {role.name} wurde dem User zugewiesen."}


@router.delete("/{user_id}/roles/{role_name}")
def remove_role(
    user_id: int,
    role_name: RoleName,
    session: Session = Depends(get_session),
    admin_user: User = Depends(require_role(RoleName.ADMIN)),
):

    user = get_user_by_id(session=session, user_id=user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User nicht gefunden"
        )

    role = get_role_by_name(session=session, name=role_name.value)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Rolle nicht gefunden"
        )

    remove_role_from_user(session=session, user=user, role=role)

    return {"message": f"Rolle {role.name} wurde vom User entfernt."}
