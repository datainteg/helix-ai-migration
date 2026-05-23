from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.auth.jwt import get_current_user_id
from app.db.session import get_db
from app.models.identity import OrganizationMember, Role, User
from app.services.auth_service import get_current_user


def get_current_user_dependency(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> User:
    return get_current_user(db, user_id)


def _active_membership(db: Session, user_id: str) -> OrganizationMember:
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.user_id == user_id,
            OrganizationMember.status == "active",
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No active organization membership")
    return membership


def get_current_organization_id(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> str:
    return _active_membership(db, user_id).organization_id


def _role_for_membership(db: Session, membership: OrganizationMember) -> Role:
    role = (
        db.query(Role)
        .options(selectinload(Role.permissions))
        .filter(Role.id == membership.role_id)
        .first()
    )
    if not role:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role not found")
    return role


def user_has_permission(db: Session, user_id: str, permission_name: str) -> bool:
    user = get_current_user(db, user_id)
    if user.is_super_admin:
        return True

    membership = _active_membership(db, user_id)
    role = _role_for_membership(db, membership)
    return any(permission.code == permission_name for permission in role.permissions)


def user_has_role(db: Session, user_id: str, role_names: set[str]) -> bool:
    user = get_current_user(db, user_id)
    if user.is_super_admin:
        return True

    membership = _active_membership(db, user_id)
    role = _role_for_membership(db, membership)
    return role.name in role_names


def require_permission(permission_name: str) -> Callable:
    def dependency(
        user_id: str = Depends(get_current_user_id),
        db: Session = Depends(get_db),
    ) -> str:
        if not user_has_permission(db, user_id, permission_name):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return user_id

    return dependency


def require_role(*role_names: str) -> Callable:
    allowed_roles = set(role_names)

    def dependency(
        user_id: str = Depends(get_current_user_id),
        db: Session = Depends(get_db),
    ) -> str:
        if not user_has_role(db, user_id, allowed_roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return user_id

    return dependency


require_admin = require_role("super_admin", "admin")
