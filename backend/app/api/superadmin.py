"""Super-admin endpoints: manage all orgs, impersonate, global stats."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db
from app.auth.jwt import get_current_user_id, create_access_token
from app.models.identity import Organization, User, OrganizationMember
from app.services.auth_service import get_current_user
from app.rate_limiting import limiter
from app.api.audit import write_audit

router = APIRouter(prefix="/superadmin", tags=["superadmin"])


def _audit_super(db: Session, admin: User, action: str, entity_type: str = "", entity_id: str = "", meta: dict | None = None, request: Request | None = None) -> None:
    """Write an audit log row for every super-admin action.

    Super-admin actions cross org boundaries, so we record them against the
    sentinel `platform` org bucket. Audit chain integrity is preserved
    per-bucket so platform-level actions form a separate chain.
    """
    try:
        write_audit(db, org_id="platform", actor_id=admin.id, action=action,
                    entity_type=entity_type, entity_id=entity_id, meta=meta, request=request)
    except Exception:
        # Audit must never block the action; failures get logged elsewhere.
        pass


def _require_super_admin(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)) -> User:
    user = get_current_user(db, user_id)
    if not user.is_super_admin:
        raise HTTPException(status_code=403, detail="Super admin access required")
    return user


@router.get("/organizations")
def list_all_orgs(request: Request, admin: User = Depends(_require_super_admin), db: Session = Depends(get_db)):
    """List all organizations across the platform."""
    _audit_super(db, admin, "super_list_orgs", request=request)
    orgs = db.query(Organization).all()
    return [
        {
            "id": o.id,
            "name": o.name,
            "slug": o.slug,
            "status": o.status,
            "member_count": db.query(OrganizationMember).filter(OrganizationMember.organization_id == o.id).count(),
            "created_at": str(o.created_at),
        }
        for o in orgs
    ]


@router.patch("/organizations/{org_id}/status")
def set_org_status(
    request: Request,
    org_id: str,
    status: str,
    admin: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Suspend or reactivate an organization."""
    if status not in ("active", "suspended"):
        raise HTTPException(status_code=400, detail="status must be 'active' or 'suspended'")
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    org.status = status
    db.commit()
    _audit_super(db, admin, "super_set_org_status", entity_type="organization",
                 entity_id=org_id, meta={"status": status}, request=request)
    return {"id": org_id, "status": status}


@router.get("/users")
def list_all_users(request: Request, admin: User = Depends(_require_super_admin), db: Session = Depends(get_db)):
    """List all users across the platform."""
    _audit_super(db, admin, "super_list_users", request=request)
    users = db.query(User).all()
    return [
        {"id": u.id, "email": u.email, "name": u.name, "status": u.status, "is_super_admin": u.is_super_admin, "created_at": str(u.created_at)}
        for u in users
    ]


class ImpersonateRequest(BaseModel):
    user_id: str
    reason: str


@router.post("/impersonate")
@limiter.limit("5/minute")
def impersonate_user(
    request: Request,
    data: ImpersonateRequest,
    admin: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Issue a short-lived token to act as another user (audit trail mandatory)."""
    import logging
    target = db.query(User).filter(User.id == data.user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    logging.getLogger(__name__).warning(
        "SUPERADMIN_IMPERSONATE admin=%s target=%s reason=%s",
        admin.id, data.user_id, data.reason,
    )
    from datetime import timedelta
    # imp_by claim ties the impersonation token back to the originating
    # super-admin. Downstream code can detect impersonation by checking for
    # this claim and surface it in audit metadata.
    token = create_access_token(
        data.user_id,
        expires_delta=timedelta(minutes=15),
        extra_claims={"imp_by": admin.id, "imp_reason": data.reason[:255]},
    )
    _audit_super(db, admin, "super_impersonate",
                 entity_type="user", entity_id=data.user_id,
                 meta={"reason": data.reason}, request=request)
    return {"access_token": token, "token_type": "bearer", "expires_in": 900, "note": "15-minute impersonation token"}


@router.get("/stats")
def platform_stats(request: Request, admin: User = Depends(_require_super_admin), db: Session = Depends(get_db)):
    """Platform-wide aggregate stats."""
    _audit_super(db, admin, "super_platform_stats", request=request)
    from app.models.project import Project
    from app.models.workflow import WorkflowRun
    return {
        "orgs": db.query(Organization).count(),
        "users": db.query(User).count(),
        "projects": db.query(Project).count(),
        "workflows": db.query(WorkflowRun).count(),
    }
