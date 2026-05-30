"""Admin RBAC service — org members, role assignment, and editable roles.

All operations are org-scoped. Guardrails prevent an org from locking itself
out: you can't strip the last admin, demote yourself out of admin, or edit the
super_admin / system roles' permissions.

System roles (is_system=True) are protected: their permissions can't be edited
and they can't be deleted. Admins create custom roles and toggle permissions on
those instead.
"""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload

from app.models.identity import User, Role, Permission, OrganizationMember
from app.services.auth_service import SYSTEM_PERMISSIONS

# Roles that grant administrative control of users/roles — used to detect the
# "last admin" condition so an org can never lock itself out.
_ADMIN_ROLE_NAMES = {"super_admin", "admin"}


# --------------------------------- members ---------------------------------

def list_members(db: Session, org_id: str) -> list[dict]:
    rows = (
        db.query(OrganizationMember)
        .options(selectinload(OrganizationMember.user))
        .filter(OrganizationMember.organization_id == org_id)
        .all()
    )
    roles = {r.id: r.name for r in db.query(Role).filter(Role.organization_id == org_id).all()}
    out = []
    for m in rows:
        u = m.user
        out.append({
            "user_id": m.user_id,
            "membership_id": m.id,
            "email": u.email if u else None,
            "name": u.name if u else None,
            "role_id": m.role_id,
            "role": roles.get(m.role_id, "—"),
            "status": m.status,
            "is_super_admin": bool(u.is_super_admin) if u else False,
        })
    out.sort(key=lambda r: (r["status"] != "active", (r["email"] or "")))
    return out


def _role_in_org(db: Session, org_id: str, role_id: str) -> Role:
    role = (
        db.query(Role)
        .filter(Role.id == role_id, Role.organization_id == org_id)
        .first()
    )
    if not role:
        raise HTTPException(status_code=404, detail="Role not found in this organization")
    return role


def _admin_member_count(db: Session, org_id: str, exclude_user_id: Optional[str] = None) -> int:
    """Active members whose role is admin/super_admin."""
    admin_role_ids = {
        r.id for r in db.query(Role)
        .filter(Role.organization_id == org_id, Role.name.in_(_ADMIN_ROLE_NAMES))
        .all()
    }
    if not admin_role_ids:
        return 0
    q = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.status == "active",
            OrganizationMember.role_id.in_(admin_role_ids),
        )
    )
    if exclude_user_id:
        q = q.filter(OrganizationMember.user_id != exclude_user_id)
    return q.count()


def change_member_role(db: Session, org_id: str, actor_user_id: str, target_user_id: str, new_role_id: str) -> dict:
    membership = (
        db.query(OrganizationMember)
        .filter(OrganizationMember.organization_id == org_id, OrganizationMember.user_id == target_user_id)
        .first()
    )
    if not membership:
        raise HTTPException(status_code=404, detail="User is not a member of this organization")

    new_role = _role_in_org(db, org_id, new_role_id)
    old_role = db.query(Role).filter(Role.id == membership.role_id).first()
    old_is_admin = old_role is not None and old_role.name in _ADMIN_ROLE_NAMES
    new_is_admin = new_role.name in _ADMIN_ROLE_NAMES

    # Guardrail: demoting the last admin (incl. demoting yourself) is refused.
    if old_is_admin and not new_is_admin:
        remaining = _admin_member_count(db, org_id, exclude_user_id=target_user_id)
        if remaining == 0:
            raise HTTPException(status_code=400, detail="Can't remove the last admin — the org would lock itself out.")

    membership.role_id = new_role.id
    db.commit()
    db.refresh(membership)
    return {"user_id": target_user_id, "role_id": new_role.id, "role": new_role.name}


# ---------------------------------- roles -----------------------------------

def _role_dict(role: Role) -> dict:
    return {
        "id": role.id,
        "name": role.name,
        "is_system": role.is_system,
        "permissions": sorted(p.code for p in role.permissions),
        "count": len(role.permissions),
    }


def list_roles(db: Session, org_id: str) -> dict:
    roles = (
        db.query(Role)
        .options(selectinload(Role.permissions))
        .filter(Role.organization_id == org_id)
        .order_by(Role.is_system.desc(), Role.name)
        .all()
    )
    # member count per role for the UI
    counts: dict[str, int] = {}
    for m in db.query(OrganizationMember).filter(OrganizationMember.organization_id == org_id).all():
        counts[m.role_id] = counts.get(m.role_id, 0) + 1
    out = []
    for r in roles:
        d = _role_dict(r)
        d["members"] = counts.get(r.id, 0)
        out.append(d)
    return {"permissions": SYSTEM_PERMISSIONS, "roles": out}


def create_role(db: Session, org_id: str, name: str, permission_codes: list[str]) -> dict:
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Role name is required")
    exists = (
        db.query(Role)
        .filter(Role.organization_id == org_id, Role.name == name)
        .first()
    )
    if exists:
        raise HTTPException(status_code=409, detail=f"A role named '{name}' already exists")
    role = Role(organization_id=org_id, name=name, scope="organization", is_system=False)
    db.add(role)
    db.flush()
    _set_role_permissions(db, role, permission_codes)
    db.commit()
    db.refresh(role)
    return _role_dict(role)


def update_role_permissions(db: Session, org_id: str, role_id: str, permission_codes: list[str]) -> dict:
    role = _role_in_org(db, org_id, role_id)
    if role.is_system:
        raise HTTPException(status_code=400, detail="System roles are protected and can't be edited. Create a custom role instead.")
    _set_role_permissions(db, role, permission_codes)
    db.commit()
    db.refresh(role)
    return _role_dict(role)


def delete_role(db: Session, org_id: str, role_id: str) -> None:
    role = _role_in_org(db, org_id, role_id)
    if role.is_system:
        raise HTTPException(status_code=400, detail="System roles can't be deleted.")
    in_use = (
        db.query(OrganizationMember)
        .filter(OrganizationMember.organization_id == org_id, OrganizationMember.role_id == role_id)
        .count()
    )
    if in_use:
        raise HTTPException(status_code=400, detail=f"This role is assigned to {in_use} member(s). Reassign them first.")
    db.delete(role)
    db.commit()


def _set_role_permissions(db: Session, role: Role, permission_codes: list[str]) -> None:
    valid = set(SYSTEM_PERMISSIONS)
    codes = [c for c in dict.fromkeys(permission_codes) if c in valid]  # dedupe + validate
    perms = db.query(Permission).filter(Permission.code.in_(codes)).all() if codes else []
    role.permissions = perms
