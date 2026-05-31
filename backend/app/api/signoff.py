"""Business sign-off API.

Draft → (edit) → send → mark approved/rejected. Email is never auto-sent; the
user creates a draft, edits it, and explicitly sends. RBAC: draft/edit/send need
project:write; recording the business decision (mark approved/rejected) needs
agent:approve. SMTP secrets are never exposed (handled by the email service).
"""
from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.dependencies import get_current_organization_id, require_permission
from app.services.project_service import ensure_project_access
from app.services import signoff_service as svc
from app.schemas.lifecycle import StageActionRequest

router = APIRouter(tags=["signoff"])


class SignoffDraftCreate(BaseModel):
    recon_report_id: str | None = None


class SignoffUpdate(BaseModel):
    recipient_email: str | None = Field(default=None, max_length=255)
    subject: str | None = Field(default=None, max_length=500)
    body: str | None = None


def _so(s) -> dict:
    return {
        "id": s.id, "project_id": s.project_id, "recon_report_id": s.recon_report_id,
        "recipient_email": s.recipient_email, "subject": s.subject, "body": s.body,
        "attachment_paths": s.attachment_paths_json or [], "status": s.status,
        "sent_at": str(s.sent_at) if s.sent_at else None,
        "approved_at": str(s.approved_at) if s.approved_at else None,
        "created_by_user_id": s.created_by_user_id,
        "created_at": str(s.created_at) if s.created_at else None,
    }


@router.post("/projects/{project_id}/signoff/draft", status_code=201)
def create_draft(project_id: str, data: SignoffDraftCreate = Body(default=SignoffDraftCreate()),
                 org_id: str = Depends(get_current_organization_id),
                 user_id: str = Depends(require_permission("project:write")), db: Session = Depends(get_db)):
    ensure_project_access(db, org_id, project_id)
    return _so(svc.create_draft(db, org_id, project_id, user_id, data.recon_report_id))


@router.get("/projects/{project_id}/signoff")
def list_signoffs(project_id: str, org_id: str = Depends(get_current_organization_id),
                  user_id: str = Depends(require_permission("project:read")), db: Session = Depends(get_db)):
    ensure_project_access(db, org_id, project_id)
    return [_so(s) for s in svc.list_signoffs(db, org_id, project_id)]


@router.get("/signoff/{signoff_id}")
def get_signoff(signoff_id: str, org_id: str = Depends(get_current_organization_id),
                user_id: str = Depends(require_permission("project:read")), db: Session = Depends(get_db)):
    return _so(svc.get_signoff(db, org_id, signoff_id))


@router.patch("/signoff/{signoff_id}")
def update_signoff(signoff_id: str, data: SignoffUpdate,
                   org_id: str = Depends(get_current_organization_id),
                   user_id: str = Depends(require_permission("project:write")), db: Session = Depends(get_db)):
    return _so(svc.update_draft(db, org_id, signoff_id, user_id,
                                recipient_email=data.recipient_email, subject=data.subject, body=data.body))


@router.post("/signoff/{signoff_id}/send")
async def send_signoff(signoff_id: str, org_id: str = Depends(get_current_organization_id),
                       user_id: str = Depends(require_permission("project:write")), db: Session = Depends(get_db)):
    return _so(await svc.send_signoff(db, org_id, signoff_id, user_id))


@router.post("/signoff/{signoff_id}/mark-approved")
def mark_approved(signoff_id: str, data: StageActionRequest = Body(default=StageActionRequest()),
                  org_id: str = Depends(get_current_organization_id),
                  user_id: str = Depends(require_permission("agent:approve")), db: Session = Depends(get_db)):
    return _so(svc.mark_approved(db, org_id, signoff_id, user_id, data.comment))


@router.post("/signoff/{signoff_id}/mark-rejected")
def mark_rejected(signoff_id: str, data: StageActionRequest = Body(default=StageActionRequest()),
                  org_id: str = Depends(get_current_organization_id),
                  user_id: str = Depends(require_permission("agent:approve")), db: Session = Depends(get_db)):
    return _so(svc.mark_rejected(db, org_id, signoff_id, user_id, data.comment))
