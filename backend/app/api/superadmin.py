"""Super-admin endpoints: manage all orgs, impersonate, global stats."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db
from app.auth.jwt import get_current_user_id, create_access_token
from app.models.identity import Organization, User, OrganizationMember
from app.services.auth_service import get_current_user
from app.rate_limiting import limiter
from app.api.audit import write_audit

# NOTE: Prefix is intentionally declared here AND mounted under /api/v1 in
# main.py so the final URL is /api/v1/superadmin/.... Every other router
# leaves prefix off and relies on main.py to mount it; superadmin is the
# only exception. Do not "harmonise" by moving it — see REVIEW_API_CONTRACT
# §1 API-C1 (CRITICAL). The smoke test in test_api_contract_pagination.py
# asserts the full path is reachable so accidental removal will fail CI.
router = APIRouter(tags=["superadmin"])

# SC-032: dedicated sentinel org id for the platform-level (super-admin) audit
# chain. The previous string literal "platform" could collide with a tenant
# org whose id was the string "platform" (org ids are UUID-typed in the model
# but several call sites stringify them). A fixed all-zero UUID can never be
# minted as a real org id, so the super-admin chain is isolated.
_PLATFORM_AUDIT_ORG_ID = "00000000-0000-0000-0000-000000000000"


def _audit_super(db: Session, admin: User, action: str, entity_type: str = "", entity_id: str = "", meta: dict | None = None, request: Request | None = None) -> None:
    """Write an audit log row for every super-admin action.

    Super-admin actions cross org boundaries, so we record them against a
    reserved sentinel org bucket (the all-zero UUID — SC-032). Audit chain
    integrity is preserved per-bucket so platform-level actions form a
    separate chain that no tenant can ever share.
    """
    try:
        write_audit(db, org_id=_PLATFORM_AUDIT_ORG_ID, actor_id=admin.id, action=action,
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
def list_all_orgs(
    request: Request,
    admin: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List organizations across the platform.

    SC-053: paginated (default 100, max 500) — the prior unbounded `.all()`
    returned every row (30+ MB / multi-second serialisation at 100k orgs),
    a DoS-shaped foot-gun. Response stays a bare array (additive change: new
    `limit`/`offset` query params with backward-compatible defaults).
    """
    _audit_super(db, admin, "super_list_orgs", request=request)
    orgs = (
        db.query(Organization)
        .order_by(Organization.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    # `.isoformat()` produces ISO-8601 ("2026-05-26T14:33:21+00:00"); the
    # previous `str(datetime)` repr lacked the "T" separator and broke
    # Safari's `Date` parser (API-C3).
    return [
        {
            "id": o.id,
            "name": o.name,
            "slug": o.slug,
            "status": o.status,
            "member_count": db.query(OrganizationMember).filter(OrganizationMember.organization_id == o.id).count(),
            "created_at": o.created_at.isoformat() if o.created_at else None,
        }
        for o in orgs
    ]


class OrgStatusUpdate(BaseModel):
    # Body-based mutation (REVIEW_API_CONTRACT §superadmin.py HIGH):
    # query-string mutations leak into proxy / access logs.
    status: str  # "active" | "suspended" — validated below.


class OrgStatusResponse(BaseModel):
    id: str
    status: str


@router.patch("/organizations/{org_id}/status", response_model=OrgStatusResponse)
def set_org_status(
    request: Request,
    org_id: str,
    data: OrgStatusUpdate,
    admin: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Suspend or reactivate an organization.

    Status flows in the JSON body (not as a query param) so values don't
    leak through proxy access logs.
    """
    if data.status not in ("active", "suspended"):
        raise HTTPException(
            status_code=422,
            detail={"message": "status must be 'active' or 'suspended'",
                    "allowed": ["active", "suspended"], "received": data.status},
        )
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    org.status = data.status
    db.commit()
    _audit_super(db, admin, "super_set_org_status", entity_type="organization",
                 entity_id=org_id, meta={"status": data.status}, request=request)
    return OrgStatusResponse(id=org_id, status=data.status)


@router.get("/users")
def list_all_users(
    request: Request,
    admin: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List users across the platform.

    SC-053: paginated (default 100, max 500). Bare-array response preserved;
    `limit`/`offset` are additive query params with safe defaults.
    """
    _audit_super(db, admin, "super_list_users", request=request)
    users = (
        db.query(User)
        .order_by(User.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": u.id,
            "email": u.email,
            "name": u.name,
            "status": u.status,
            "is_super_admin": u.is_super_admin,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
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
