"""Admin RBAC API — org members, role assignment, and editable roles.

Org-scoped. Reads need admin:users:read / admin:roles:read; writes need the
matching :write permission. System roles are protected; lockout guardrails live
in admin_rbac_service.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.dependencies import require_permission, resolve_active_org_id
from app.api.audit import write_audit
from app.services import admin_rbac_service as rbac

router = APIRouter(tags=["admin-rbac"])


# ---- users / members ----

@router.get("/admin/users")
def list_users(
    user_id: str = Depends(require_permission("admin:users:read")),
    db: Session = Depends(get_db),
):
    org_id = resolve_active_org_id(db, user_id)
    return rbac.list_members(db, org_id)


class ChangeRoleRequest(BaseModel):
    role_id: str = Field(min_length=1)


@router.put("/admin/users/{target_user_id}/role")
def change_role(
    target_user_id: str,
    data: ChangeRoleRequest,
    request: Request,
    user_id: str = Depends(require_permission("admin:users:write")),
    db: Session = Depends(get_db),
):
    org_id = resolve_active_org_id(db, user_id)
    result = rbac.change_member_role(db, org_id, user_id, target_user_id, data.role_id)
    write_audit(db, org_id=org_id, actor_id=user_id, action="member_role_changed",
                entity_type="organization_member", entity_id=target_user_id,
                meta={"role_id": data.role_id}, request=request)
    return result


# ---- roles ----

@router.get("/admin/roles")
def list_roles(
    user_id: str = Depends(require_permission("admin:roles:read")),
    db: Session = Depends(get_db),
):
    org_id = resolve_active_org_id(db, user_id)
    return rbac.list_roles(db, org_id)


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    permissions: list[str] = Field(default_factory=list)


class RolePermsUpdate(BaseModel):
    permissions: list[str] = Field(default_factory=list)


@router.post("/admin/roles", status_code=201)
def create_role(
    data: RoleCreate,
    request: Request,
    user_id: str = Depends(require_permission("admin:roles:write")),
    db: Session = Depends(get_db),
):
    org_id = resolve_active_org_id(db, user_id)
    role = rbac.create_role(db, org_id, data.name, data.permissions)
    write_audit(db, org_id=org_id, actor_id=user_id, action="role_created",
                entity_type="role", entity_id=role["id"],
                meta={"name": role["name"]}, request=request)
    return role


@router.put("/admin/roles/{role_id}/permissions")
def update_role_perms(
    role_id: str,
    data: RolePermsUpdate,
    request: Request,
    user_id: str = Depends(require_permission("admin:roles:write")),
    db: Session = Depends(get_db),
):
    org_id = resolve_active_org_id(db, user_id)
    role = rbac.update_role_permissions(db, org_id, role_id, data.permissions)
    write_audit(db, org_id=org_id, actor_id=user_id, action="role_permissions_updated",
                entity_type="role", entity_id=role_id,
                meta={"count": role["count"]}, request=request)
    return role


@router.delete("/admin/roles/{role_id}", status_code=204)
def delete_role(
    role_id: str,
    request: Request,
    user_id: str = Depends(require_permission("admin:roles:write")),
    db: Session = Depends(get_db),
):
    org_id = resolve_active_org_id(db, user_id)
    rbac.delete_role(db, org_id, role_id)
    write_audit(db, org_id=org_id, actor_id=user_id, action="role_deleted",
                entity_type="role", entity_id=role_id, request=request)
