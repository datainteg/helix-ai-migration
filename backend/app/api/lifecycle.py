"""Stage-gated lifecycle API.

RBAC: running/submitting/resubmitting/skipping/advancing a stage needs
project:write; approve/reject/request-changes needs agent:approve (the approver
role). Everything is org/project-isolated + audited via the service layer.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.jwt import get_current_user_id
from app.auth.dependencies import get_current_organization_id, require_permission, user_has_role
from app.services.project_service import ensure_project_access

# Admins/super-admins are exempt from the stage separation-of-duties rule
# (they may self-approve); a plain project_manager cannot approve what they
# themselves submitted.
_SOD_BYPASS_ROLES = {"super_admin", "admin"}
from app.services import stage_lifecycle_service as svc
from app.schemas.lifecycle import (
    StageActionRequest, StageRejectRequest, StageSkipRequest, StageResubmitRequest,
    stage_to_dict,
)

router = APIRouter(tags=["lifecycle"])


@router.get("/projects/{project_id}/lifecycle")
def get_lifecycle(project_id: str, org_id: str = Depends(get_current_organization_id), user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    ensure_project_access(db, org_id, project_id)
    return [stage_to_dict(s) for s in svc.get_project_lifecycle(db, org_id, project_id)]


@router.get("/projects/{project_id}/lifecycle/transitions")
def get_transitions(project_id: str, org_id: str = Depends(get_current_organization_id), user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    ensure_project_access(db, org_id, project_id)
    return [
        {
            "id": t.id, "stage_id": t.stage_id, "from_status": t.from_status, "to_status": t.to_status,
            "action": t.action, "actor_type": t.actor_type, "actor_id": t.actor_id, "comment": t.comment,
            "created_at": str(t.created_at) if t.created_at else None,
        }
        for t in svc.get_stage_transitions(db, org_id, project_id)
    ]


@router.get("/projects/{project_id}/lifecycle/current")
def get_current(project_id: str, org_id: str = Depends(get_current_organization_id), user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    ensure_project_access(db, org_id, project_id)
    cur = svc.get_current_stage(db, org_id, project_id)
    return stage_to_dict(cur) if cur else None


@router.post("/projects/{project_id}/lifecycle/initialize")
def initialize(project_id: str, org_id: str = Depends(get_current_organization_id), user_id: str = Depends(require_permission("project:write")), db: Session = Depends(get_db)):
    ensure_project_access(db, org_id, project_id)
    stages = svc.initialize_project_lifecycle(db, org_id, project_id, actor_user_id=user_id)
    return [stage_to_dict(s) for s in stages]


@router.post("/projects/{project_id}/lifecycle/{stage_key}/start")
def start(project_id: str, stage_key: str, org_id: str = Depends(get_current_organization_id), user_id: str = Depends(require_permission("project:write")), db: Session = Depends(get_db)):
    ensure_project_access(db, org_id, project_id)
    return stage_to_dict(svc.start_stage(db, org_id, project_id, stage_key, user_id))


@router.post("/projects/{project_id}/lifecycle/{stage_key}/submit-review")
def submit_review(project_id: str, stage_key: str, data: StageActionRequest, org_id: str = Depends(get_current_organization_id), user_id: str = Depends(require_permission("project:write")), db: Session = Depends(get_db)):
    ensure_project_access(db, org_id, project_id)
    return stage_to_dict(svc.submit_stage_for_review(db, org_id, project_id, stage_key, data.artifact_id, user_id))


@router.post("/projects/{project_id}/lifecycle/{stage_key}/approve")
def approve(project_id: str, stage_key: str, data: StageActionRequest, org_id: str = Depends(get_current_organization_id), user_id: str = Depends(require_permission("agent:approve")), db: Session = Depends(get_db)):
    ensure_project_access(db, org_id, project_id)
    allow_self = user_has_role(db, user_id, _SOD_BYPASS_ROLES)
    return stage_to_dict(svc.approve_stage(db, org_id, project_id, stage_key, user_id, data.comment, allow_self_approval=allow_self))


@router.post("/projects/{project_id}/lifecycle/{stage_key}/reject")
def reject(project_id: str, stage_key: str, data: StageRejectRequest, org_id: str = Depends(get_current_organization_id), user_id: str = Depends(require_permission("agent:approve")), db: Session = Depends(get_db)):
    ensure_project_access(db, org_id, project_id)
    return stage_to_dict(svc.reject_stage(db, org_id, project_id, stage_key, user_id, data.comment))


@router.post("/projects/{project_id}/lifecycle/{stage_key}/request-changes")
def request_changes(project_id: str, stage_key: str, data: StageRejectRequest, org_id: str = Depends(get_current_organization_id), user_id: str = Depends(require_permission("agent:approve")), db: Session = Depends(get_db)):
    ensure_project_access(db, org_id, project_id)
    return stage_to_dict(svc.request_stage_changes(db, org_id, project_id, stage_key, user_id, data.comment))


@router.post("/projects/{project_id}/lifecycle/{stage_key}/resubmit")
def resubmit(project_id: str, stage_key: str, data: StageResubmitRequest, org_id: str = Depends(get_current_organization_id), user_id: str = Depends(require_permission("project:write")), db: Session = Depends(get_db)):
    ensure_project_access(db, org_id, project_id)
    return stage_to_dict(svc.resubmit_stage(db, org_id, project_id, stage_key, data.artifact_version_id, user_id))


@router.post("/projects/{project_id}/lifecycle/{stage_key}/skip")
def skip(project_id: str, stage_key: str, data: StageSkipRequest, org_id: str = Depends(get_current_organization_id), user_id: str = Depends(require_permission("project:write")), db: Session = Depends(get_db)):
    ensure_project_access(db, org_id, project_id)
    return stage_to_dict(svc.skip_optional_stage(db, org_id, project_id, stage_key, user_id, data.reason))


@router.post("/projects/{project_id}/lifecycle/{stage_key}/complete")
def complete(project_id: str, stage_key: str, org_id: str = Depends(get_current_organization_id), user_id: str = Depends(require_permission("project:write")), db: Session = Depends(get_db)):
    """Complete a non-agent stage (sprint execution / sign-off / closure) and
    advance the lifecycle. Agent stages must be approved, not completed."""
    ensure_project_access(db, org_id, project_id)
    return stage_to_dict(svc.complete_stage(db, org_id, project_id, stage_key, user_id))


@router.post("/projects/{project_id}/lifecycle/advance")
def advance(project_id: str, org_id: str = Depends(get_current_organization_id), user_id: str = Depends(require_permission("project:write")), db: Session = Depends(get_db)):
    ensure_project_access(db, org_id, project_id)
    nxt = svc.advance_to_next_stage(db, org_id, project_id)
    return stage_to_dict(nxt) if nxt else None
