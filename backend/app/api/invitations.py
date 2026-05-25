from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, field_validator

from app.db.session import get_db
from app.auth.jwt import get_current_user_id
from app.auth.dependencies import require_permission
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
# `admin` and `super_admin` are intentionally excluded — promoting someone to
# admin must go through the super-admin promotion endpoint, not an invite.
_INVITABLE_ROLES = {"viewer", "editor", "developer", "analyst"}


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


@router.post("/invitations", status_code=201)
@limiter.limit("20/minute")
async def invite_user(
    request: Request,
    data: InviteRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(require_permission("admin:users:write")),
    db: Session = Depends(get_db),
):
    user = get_current_user(db, user_id)
    org_id = str(user.memberships[0].organization_id)
    raw_token = create_invitation(db, org_id, user_id, data.email, data.role)

    invite_url = f"{settings.FRONTEND_URL}/accept-invite?token={raw_token}"
    from app.services.email_service import send_email, render_invitation_email
    org_name = user.memberships[0].organization.name if user.memberships[0].organization else "Helix"
    subject, html = render_invitation_email(user.name, org_name, invite_url)
    background_tasks.add_task(send_email, to=data.email, subject=subject, html_body=html)

    return {"status": "invited", "email": data.email}


@router.post("/invitations/accept", response_model=TokenResponse)
@limiter.limit("10/minute")
def accept_invite(request: Request, data: AcceptInviteRequest, db: Session = Depends(get_db)):
    return accept_invitation(db, data.token, data.name, data.password)


@router.get("/invitations")
def get_invitations(
    user_id: str = Depends(require_permission("admin:users:read")),
    db: Session = Depends(get_db),
):
    user = get_current_user(db, user_id)
    org_id = str(user.memberships[0].organization_id)
    invites = list_invitations(db, org_id)
    return [
        {
            "id": i.id,
            "email": i.email,
            "status": i.status,
            "expires_at": str(i.expires_at),
            "accepted_at": str(i.accepted_at) if i.accepted_at else None,
        }
        for i in invites
    ]


@router.delete("/invitations/{invitation_id}", status_code=204)
def delete_invitation(
    request: Request,
    invitation_id: str,
    user_id: str = Depends(require_permission("admin:users:write")),
    db: Session = Depends(get_db),
):
    user = get_current_user(db, user_id)
    if not user.memberships:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="User has no organization membership")
    org_id = str(user.memberships[0].organization_id)
    revoke_invitation(db, org_id, invitation_id)
    write_audit(db, org_id=org_id, actor_id=user_id, action="invitation_revoked",
                entity_type="invitation", entity_id=invitation_id, request=request)
