"""Agent workflow API — start and monitor BMAD planning workflows."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db
from app.auth.jwt import get_current_user_id
from app.auth.dependencies import get_current_organization_id
from app.services.project_service import ensure_project_access
from app.services.workflow_service import (
    get_workflow_run,
    get_workflow_status,
    list_workflow_runs,
    start_bmad_planning_workflow,
    update_workflow_run_status,
)
from app.models.project import MigrationRequirement
from app.api.audit import write_audit


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
    request: Request,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Record a human approval decision for a workflow step."""
    run = get_workflow_run(db, workflow_id)
    if not run:
        raise HTTPException(status_code=404, detail="Workflow not found")

    new_status = "approved" if data.decision == "approved" else "rejected"
    update_workflow_run_status(db, workflow_id, new_status)

    write_audit(
        db,
        org_id=org_id,
        actor_id=user_id,
        action=f"workflow_{new_status}",
        entity_type="workflow_run",
        entity_id=workflow_id,
        meta={"decision": data.decision, "notes": data.notes},
        request=request,
    )

    return {
        "workflow_id": workflow_id,
        "decision": data.decision,
        "status": new_status,
    }


@router.get("/projects/{project_id}/agent-workflows")
def list_workflows(
    project_id: str,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """List workflow runs for a project."""
    ensure_project_access(db, org_id, project_id)
    runs = list_workflow_runs(db, organization_id=org_id, project_id=project_id)
    return [
        {
            "workflow_id": r.workflow_id,
            "run_id": r.run_id,
            "status": r.status,
            "mode": r.mode,
            "project_id": r.project_id,
            "requirement_id": r.requirement_id,
            "created_at": str(r.created_at) if r.created_at else None,
        }
        for r in runs
    ]
