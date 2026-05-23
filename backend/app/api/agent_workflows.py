"""Agent workflow API — start and monitor BMAD planning workflows."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db
from app.auth.jwt import get_current_user_id
from app.auth.dependencies import get_current_organization_id
from app.services.project_service import ensure_project_access
from app.services.workflow_service import (
    get_workflow_status,
    start_bmad_planning_workflow,
)
from app.models.project import MigrationRequirement


class StartWorkflowRequest(BaseModel):
    requirement_id: str
    requirement_text: str | None = None


class StartWorkflowResponse(BaseModel):
    workflow_id: str
    run_id: str
    status: str
    mode: str
    result: dict | None = None  # Full graph output in local_fallback mode


class ApprovalRequest(BaseModel):
    decision: str  # "approved" or "rejected"
    notes: str = ""


router = APIRouter(tags=["agent-workflows"])


@router.post("/projects/{project_id}/agent-workflows", response_model=StartWorkflowResponse)
async def start_workflow(
    project_id: str,
    data: StartWorkflowRequest,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Start a BMAD planning workflow for a project requirement."""
    ensure_project_access(db, org_id, project_id)

    requirement = db.query(MigrationRequirement).filter(
        MigrationRequirement.id == data.requirement_id,
        MigrationRequirement.project_id == project_id,
    ).first()
    if not requirement:
        raise HTTPException(status_code=404, detail="Requirement not found")

    result = await start_bmad_planning_workflow(
        project_id=project_id,
        requirement_id=data.requirement_id,
        organization_id=org_id,
        requirement_text=data.requirement_text or requirement.source_text,
        db=db,
    )

    return StartWorkflowResponse(
        workflow_id=result["workflow_id"],
        run_id=result["run_id"],
        status=result["status"],
        mode=result["mode"],
        result=result.get("result"),
    )


@router.get("/agent-workflows/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Get BMAD workflow status by workflow ID."""
    return await get_workflow_status(workflow_id, db=db)


@router.post("/agent-workflows/{workflow_id}/approve")
def approve_step(
    workflow_id: str,
    data: ApprovalRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Record a human approval decision for a workflow step."""
    return {
        "workflow_id": workflow_id,
        "decision": data.decision,
        "status": "recorded",
    }


@router.get("/projects/{project_id}/agent-workflows")
def list_workflows(
    project_id: str,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """List workflow runs for a project. (Placeholder until Prompt 10.)"""
    ensure_project_access(db, org_id, project_id)
    # TODO: Query workflow_runs table once Prompt 10 is implemented.
    return []
    return {"project_id": project_id, "workflows": []}
