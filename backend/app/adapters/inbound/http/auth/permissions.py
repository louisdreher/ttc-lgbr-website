from typing import Annotated

from fastapi import Depends, HTTPException

from app.adapters.inbound.http.auth.dependencies import get_current_user
from app.core.users.public import RoleName, UserDetails


def require_any_role(*required_roles: RoleName):
    def role_checker(
        current_user: Annotated[UserDetails, Depends(get_current_user)],
    ) -> UserDetails:
        if set(current_user.roles).isdisjoint(role.value for role in required_roles):
            raise HTTPException(status_code=403, detail="Keine Berechtigung")
        return current_user

    return role_checker


def require_role(required_role: RoleName):
    return require_any_role(required_role)
