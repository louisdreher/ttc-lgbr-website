from app.auth.dependencies import get_current_user
from fastapi import Depends, HTTPException, status

from backend.app.domains.users.model import RoleName, User


def require_role(required_role: RoleName):

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        has_role = any(role.name == required_role.value for role in current_user.roles)
        if not has_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Keine Berechtigung"
            )
        return current_user

    return role_checker


def require_any_role(*required_roles: RoleName):

    def role_checker(current_user: User = Depends(get_current_user)) -> User:

        required_role_names = {role.value for role in required_roles}

        user_role_names = {role.name for role in current_user.roles}

        if user_role_names.isdisjoint(required_role_names):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Keine Berechtigung"
            )

        return current_user

    return role_checker
