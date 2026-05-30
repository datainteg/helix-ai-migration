from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, field_validator

from app.db.session import get_db
from app.security.password_policy import validate_password
from app.auth.jwt import get_current_user_id
from app.auth.dependencies import (
    require_permission,
    resolve_active_membership,
    resolve_active_org_id,
)
from app.services.auth_service import get_current_user
from app.services.invitation_service import (
    create_invitation, accept_invitation, list_invitations, revoke_invitation,
)
from app.schemas.identity import TokenResponse
from app.core.config import settings
from app.rate_limiting import limiter
from app.api.audit import write_audit

router = APIRouter(tags=["invitations"])


# Roles a non-super-admin caller is allowed to grant via invitation.
# Non-admin system roles a member can be invited as. MUST match real role names
# in auth_service.SYSTEM_ROLES — create_invitation resolves the Role by name, so
# a name with no matching Role row would orphan the invite on accept.
# `admin` and `super_admin` are intentionally excluded — promoting someone to
# admin must go through role assignment after they join, not an invite.
_INVITABLE_ROLES = {"viewer", "project_manager", "architect", "data_engineer", "qa_engineer"}


class InviteRequest(BaseModel):
    email: EmailStr
    role: str = "viewer"

    @field_validator("role")
    @classmethod
    def _restrict_role(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if v not in _INVITABLE_ROLES:
            raise ValueError(
                f"role must be one of {sorted(_INVITABLE_ROLES)}; "
                "admin / super_admin require platform-admin promotion"
            )
        return v


class AcceptInviteRequest(BaseModel):
    token: str
    name: str
    password: str

    @field_validator("password")
    @classmethod
    def _check_password(cls, v: str) -> str:  # SC-002
        return validate_password(v)


class InvitationCreated(BaseModel):
    """201 response shape for POST /invitations."""

    status: str
    email: str


@router.post("/invitations", status_code=201, response_model=InvitationCreated)
@limiter.limit("20/minute")
async def invite_user(
    request: Request,
    data: InviteRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(require_permission("admin:users:write")),
    db: Session = Depends(get_db),
):
    membership = resolve_active_membership(db, user_id)
    org_id = str(membership.organization_id)
    user = get_current_user(db, user_id)  # for inviter's display name
    raw_token = create_invitation(db, org_id, user_id, data.email, data.role)

    invite_url = f"{settings.FRONTEND_URL}/accept-invite?token={raw_token}"
    from app.services.email_service import send_email, render_invitation_email
    org_name = membership.organization.name if membership.organization else "Helix"
    subject, html = render_invitation_email(user.name, org_name, invite_url)
    background_tasks.add_task(send_email, to=data.email, subject=subject, html_body=html)

    # Audit emission was missing — REVIEW_API_CONTRACT §Audit emission lists
    # invitations under the "no audit row" set.
    write_audit(
        db, org_id=org_id, actor_id=user_id,
        action="invitation_created",
        entity_type="invitation", entity_id=data.email,
        meta={"role": data.role}, request=request,
    )
    return InvitationCreated(status="invited", email=data.email)


@router.post("/invitations/accept", response_model=TokenResponse)
@limiter.limit("10/minute")
def accept_invite(request: Request, data: AcceptInviteRequest, db: Session = Depends(get_db)):
    return accept_invitation(db, data.token, data.name, data.password)


class InvitationSummary(BaseModel):
    """Row returned by `GET /invitations`. All timestamps ISO-8601."""

    id: str
    email: str
    status: str | None = None
    expires_at: str | None = None
    accepted_at: str | None = None


@router.get("/invitations", response_model=list[InvitationSummary])
def get_invitations(
    user_id: str = Depends(require_permission("admin:users:read")),
    db: Session = Depends(get_db),
):
    org_id = resolve_active_org_id(db, user_id)
    invites = list_invitations(db, org_id)
    # ISO-8601 timestamps (API-C3) — `str(datetime)` lacked the "T"
    # separator and broke Safari's Date parser.
    return [
        InvitationSummary(
            id=i.id,
            email=i.email,
            status=i.status,
            expires_at=i.expires_at.isoformat() if i.expires_at else None,
            accepted_at=i.accepted_at.isoformat() if i.accepted_at else None,
        )
        for i in invites
    ]


@router.delete("/invitations/{invitation_id}", status_code=204)
def delete_invitation(
    request: Request,
    invitation_id: str,
    user_id: str = Depends(require_permission("admin:users:write")),
    db: Session = Depends(get_db),
):
    org_id = resolve_active_org_id(db, user_id)
    revoke_invitation(db, org_id, invitation_id)
    write_audit(db, org_id=org_id, actor_id=user_id, action="invitation_revoked",
                entity_type="invitation", entity_id=invitation_id, request=request)
