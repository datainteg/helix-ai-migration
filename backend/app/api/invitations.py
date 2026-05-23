from fastapi import APIRouter, Depends, BackgroundTasks, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

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

router = APIRouter(tags=["invitations"])


class InviteRequest(BaseModel):
    email: EmailStr
    role: str = "viewer"


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
    invitation_id: str,
    user_id: str = Depends(require_permission("admin:users:write")),
    db: Session = Depends(get_db),
):
    user = get_current_user(db, user_id)
    org_id = str(user.memberships[0].organization_id)
    revoke_invitation(db, org_id, invitation_id)
