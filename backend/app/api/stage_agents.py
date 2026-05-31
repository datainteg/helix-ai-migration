"""Stage-gated agent execution API.

Short per-stage agent runs driven by the DB state machine (not a long-lived
Temporal workflow). Running a stage builds its prompt from previously APPROVED
artifacts, runs the mapped BMAD persona, stores the output as an artifact
version, and parks the stage at under_review awaiting human approval.

RBAC: all actions need project:write (running/regenerating is authoring work).
Approval itself stays on the agent:approve path in lifecycle.py. Everything is
org/project-isolated + audited via the service layer.
"""
from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.jwt import get_current_user_id  # noqa: F401  (kept for symmetry / future read endpoints)
from app.auth.dependencies import get_current_organization_id, require_permission
from app.services.project_service import ensure_project_access
from app.services import stage_agent_service as svc
from app.schemas.lifecycle import StageAgentRunRequest

router = APIRouter(tags=["stage-agents"])


@router.post("/projects/{project_id}/stages/{stage_key}/run-agent")
def run_agent(
    project_id: str,
    stage_key: str,
    data: StageAgentRunRequest = Body(default=StageAgentRunRequest()),
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(require_permission("project:write")),
    db: Session = Depends(get_db),
):
    ensure_project_access(db, org_id, project_id)
    return svc.run_stage_agent(db, org_id, project_id, stage_key, user_id, data.instructions)


@router.post("/projects/{project_id}/stages/{stage_key}/regenerate")
def regenerate(
    project_id: str,
    stage_key: str,
    data: StageAgentRunRequest = Body(default=StageAgentRunRequest()),
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(require_permission("project:write")),
    db: Session = Depends(get_db),
):
    ensure_project_access(db, org_id, project_id)
    return svc.regenerate_stage_agent(db, org_id, project_id, stage_key, user_id, data.instructions)


@router.post("/projects/{project_id}/stages/{stage_key}/continue-after-approval")
def continue_after_approval(
    project_id: str,
    stage_key: str,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(require_permission("project:write")),
    db: Session = Depends(get_db),
):
    ensure_project_access(db, org_id, project_id)
    return svc.continue_after_approval(db, org_id, project_id, stage_key, user_id)
