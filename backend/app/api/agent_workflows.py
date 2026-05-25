"""Agent workflow API — start and monitor BMAD planning workflows."""

import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
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
    request: Request,
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

    # RequestIdMiddleware sets state.request_id; propagate it into the workflow
    # so logs + artifact frontmatter + Prometheus labels share the same trace.
    correlation_id = getattr(request.state, "request_id", None) if request else None
    result = await start_bmad_planning_workflow(
        project_id=project_id,
        requirement_id=data.requirement_id,
        organization_id=org_id,
        requirement_text=data.requirement_text or requirement.source_text,
        db=db,
        correlation_id=correlation_id,
    )

    return StartWorkflowResponse(
        workflow_id=result["workflow_id"],
        run_id=result["run_id"],
        status=result["status"],
        mode=result["mode"],
        result=result.get("result"),
    )


def _assert_workflow_in_org(db: Session, workflow_id: str, org_id: str) -> None:
    """Cross-org access guard. Raises 404 if workflow belongs to a different org."""
    from app.models.workflow import WorkflowRun

    run = (
        db.query(WorkflowRun)
        .filter(WorkflowRun.workflow_id == workflow_id, WorkflowRun.organization_id == org_id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Workflow not found")


@router.get("/agent-workflows/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Get BMAD workflow status + all persisted steps + artifact paths."""
    _assert_workflow_in_org(db, workflow_id, org_id)
    return await get_workflow_status(workflow_id, db=db)


@router.get("/agent-workflows/{workflow_id}/artifacts")
async def list_workflow_artifacts(
    workflow_id: str,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Return every artifact path produced by a workflow's agents."""
    _assert_workflow_in_org(db, workflow_id, org_id)
    status = await get_workflow_status(workflow_id, db=db)
    artifacts = []
    for step in status.get("steps", []):
        if step.get("artifact_path"):
            artifacts.append({
                "agent_name": step["agent_name"],
                "step_order": step["step_order"],
                "artifact_path": step["artifact_path"],
            })
    return artifacts


@router.get("/agent-workflows/{workflow_id}/artifact-content")
async def read_workflow_artifact(
    workflow_id: str,
    path: str,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Read the raw markdown content of one artifact produced by this workflow.

    Path must match one of the artifact_paths persisted on the workflow's steps —
    guards against arbitrary filesystem reads.
    """
    import os

    _assert_workflow_in_org(db, workflow_id, org_id)
    status = await get_workflow_status(workflow_id, db=db)
    allowed_paths = {step.get("artifact_path") for step in status.get("steps", [])}
    allowed_paths.discard(None)
    if path not in allowed_paths:
        raise HTTPException(status_code=403, detail="Path not associated with this workflow")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Artifact file missing on disk")
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    return {"path": path, "content": content}


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
    _assert_workflow_in_org(db, workflow_id, org_id)

    new_status = "approved" if data.decision == "approved" else "rejected"
    update_workflow_run_status(db, workflow_id, new_status, organization_id=org_id)

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


@router.get("/agent-workflows/{workflow_id}/stream")
async def stream_workflow_progress(
    workflow_id: str,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """SSE stream of workflow step events. Client connects once; server pushes updates."""

    _assert_workflow_in_org(db, workflow_id, org_id)

    async def event_generator():
        last_step_count = 0
        for _ in range(120):  # max 2 min polling at 1s intervals
            status = await get_workflow_status(workflow_id, db=db)
            steps = status.get("steps", [])
            if len(steps) > last_step_count:
                for step in steps[last_step_count:]:
                    data = json.dumps({"type": "step", "step": step})
                    yield f"data: {data}\n\n"
                last_step_count = len(steps)

            run_status = status.get("status", "")
            if run_status in ("completed", "approved", "rejected", "failed"):
                data = json.dumps({"type": "done", "status": run_status})
                yield f"data: {data}\n\n"
                return

            await asyncio.sleep(1)
        yield f"data: {json.dumps({'type': 'timeout'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/agent-workflows/{workflow_id}/signal-approve")
async def signal_approve(
    workflow_id: str,
    data: ApprovalRequest,
    request: Request,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Send 'approve' signal to a waiting Temporal per-node workflow."""
    import os
    from temporalio.client import Client

    _assert_workflow_in_org(db, workflow_id, org_id)
    try:
        client = await Client.connect(os.getenv("TEMPORAL_ADDRESS", "localhost:7233"))
        handle = client.get_workflow_handle(workflow_id)
        await handle.signal("approve", data.notes)
        update_workflow_run_status(db, workflow_id, "approved", organization_id=org_id)
        write_audit(db, org_id=org_id, actor_id=user_id, action="workflow_signal_approved",
                    entity_type="workflow_run", entity_id=workflow_id,
                    meta={"notes": data.notes}, request=request)
        return {"workflow_id": workflow_id, "signal": "approve", "status": "sent"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Failed to signal workflow: {exc}") from exc


@router.post("/agent-workflows/{workflow_id}/signal-reject")
async def signal_reject(
    workflow_id: str,
    data: ApprovalRequest,
    request: Request,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Send 'reject' signal to a waiting Temporal per-node workflow."""
    import os
    from temporalio.client import Client

    _assert_workflow_in_org(db, workflow_id, org_id)
    try:
        client = await Client.connect(os.getenv("TEMPORAL_ADDRESS", "localhost:7233"))
        handle = client.get_workflow_handle(workflow_id)
        await handle.signal("reject", data.notes)
        update_workflow_run_status(db, workflow_id, "rejected", organization_id=org_id)
        write_audit(db, org_id=org_id, actor_id=user_id, action="workflow_signal_rejected",
                    entity_type="workflow_run", entity_id=workflow_id,
                    meta={"notes": data.notes}, request=request)
        return {"workflow_id": workflow_id, "signal": "reject", "status": "sent"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Failed to signal workflow: {exc}") from exc


@router.get("/projects/{project_id}/agent-workflows")
def list_workflows(
    project_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """List workflow runs for a project (paginated)."""
    ensure_project_access(db, org_id, project_id)
    runs = list_workflow_runs(db, organization_id=org_id, project_id=project_id)
    return _serialize_workflow_runs(runs[offset : offset + limit])


@router.get("/agent-workflows")
def list_all_workflows(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """List every workflow run for the current organization (paginated)."""
    runs = list_workflow_runs(db, organization_id=org_id)
    return _serialize_workflow_runs(runs[offset : offset + limit])


def _serialize_workflow_runs(runs) -> list[dict]:
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
