"""Sprint Management API.

Read-mostly: every page in the frontend has a corresponding GET endpoint
keyed off `project_id`. Mutations cover status updates + approval
decisions + the seed trigger. Org scope is enforced by
`ensure_project_access` at the route boundary and by the org filter
inside every service call.
"""

import asyncio
import json
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.jwt import get_current_user_id
from app.auth.dependencies import get_current_organization_id, require_permission
from app.services.project_service import ensure_project_access
from app.services.sprint_service import (
    list_sprints, get_sprint, get_active_sprint,
    list_tasks_for_sprint, update_task_status,
    list_risks_for_sprint, list_approvals_for_sprint, decide_approval,
    list_releases, get_mapping_graph, list_executions,
    compute_velocity, compute_burndown,
    create_sprint, create_task,
)
from app.services.sprint_seed import seed_sprints_for_project
from app.schemas.sprint import (
    SprintCreate, SprintResponse, SprintTaskCreate, SprintTaskResponse, SprintTaskUpdate,
    SprintRiskResponse, SprintApprovalResponse, ApprovalDecision,
    MigrationReleaseResponse, MappingGraphOut, MappingNodeOut, MappingEdgeOut,
    AgentExecutionOut, VelocityPointOut, BurndownPointOut, SeedResult,
)
from app.api.audit import write_audit


router = APIRouter(tags=["sprints"])


# ── Project-scoped lists ────────────────────────────────────────────

@router.get("/projects/{project_id}/sprints", response_model=list[SprintResponse])
def api_list_sprints(
    project_id: str,
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    ensure_project_access(db, org_id, project_id)
    return list_sprints(db, org_id, project_id)


@router.get("/projects/{project_id}/sprints/active", response_model=SprintResponse | None)
def api_active_sprint(
    project_id: str,
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    ensure_project_access(db, org_id, project_id)
    return get_active_sprint(db, org_id, project_id)


@router.get("/projects/{project_id}/sprints/velocity", response_model=list[VelocityPointOut])
def api_velocity(
    project_id: str,
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    ensure_project_access(db, org_id, project_id)
    return compute_velocity(db, org_id, project_id)


@router.get("/projects/{project_id}/sprints/mapping", response_model=MappingGraphOut)
def api_mapping(
    project_id: str,
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    ensure_project_access(db, org_id, project_id)
    nodes, edges = get_mapping_graph(db, org_id, project_id)
    return {
        "nodes": [MappingNodeOut.model_validate(n) for n in nodes],
        "edges": [MappingEdgeOut.model_validate(e) for e in edges],
    }


@router.get("/projects/{project_id}/sprints/executions", response_model=list[AgentExecutionOut])
def api_executions(
    project_id: str,
    limit: int = 50,
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    ensure_project_access(db, org_id, project_id)
    return list_executions(db, org_id, project_id, limit=limit)


@router.get("/projects/{project_id}/sprints/executions/stream")
async def api_executions_stream(
    project_id: str,
    token: str,
    db: Session = Depends(get_db),
):
    """SSE stream of agent executions. Auth via `?token=` query param
    because the browser EventSource API can't send custom headers — JWT
    is decoded inline below, then the same org-scope check applies.

    Pushes a snapshot frame every 2s with the latest 50 executions.
    Connection auto-closes after 5 minutes; EventSource auto-reconnects
    on the client by default."""
    from app.auth.jwt import decode_access_token
    from app.auth.dependencies import resolve_active_org_id

    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("missing sub")
        # Reject full-power tokens used in URLs. Frontend must trade them
        # via POST /auth/sse-ticket which returns a scope=sse short-TTL ticket.
        if payload.get("scope") != "sse":
            raise ValueError("token is not an sse ticket")
        org_id = resolve_active_org_id(db, user_id)
    except Exception:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Invalid stream token")

    ensure_project_access(db, org_id, project_id)

    async def event_generator():
        seen_ids: set[str] = set()
        # ~150 iterations * 2s = 5 minutes max
        for _ in range(150):
            rows = list_executions(db, org_id, project_id, limit=50)
            new_rows = [r for r in rows if r.id not in seen_ids]
            for r in new_rows:
                seen_ids.add(r.id)
            payload = {
                "type": "snapshot",
                "rows": [
                    {
                        "id": r.id,
                        "agent_code": r.agent_code,
                        "task_id": r.task_id,
                        "status": r.status,
                        "started_at": str(r.started_at) if r.started_at else None,
                        "duration_ms": r.duration_ms,
                        "retries": r.retries,
                        "mode": r.mode,
                        "log": r.log,
                    }
                    for r in rows
                ],
                "new_count": len(new_rows),
            }
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(2)
        yield f"data: {json.dumps({'type': 'timeout'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/projects/{project_id}/sprints/releases", response_model=list[MigrationReleaseResponse])
def api_releases(
    project_id: str,
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    ensure_project_access(db, org_id, project_id)
    return list_releases(db, org_id, project_id)


# ── Sprint-scoped lists ────────────────────────────────────────────

@router.get("/sprints/{sprint_id}", response_model=SprintResponse)
def api_get_sprint(
    sprint_id: str,
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    return get_sprint(db, org_id, sprint_id)


@router.get("/sprints/{sprint_id}/tasks", response_model=list[SprintTaskResponse])
def api_list_tasks(
    sprint_id: str,
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    return list_tasks_for_sprint(db, org_id, sprint_id)


@router.get("/sprints/{sprint_id}/risks", response_model=list[SprintRiskResponse])
def api_list_risks(
    sprint_id: str,
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    return list_risks_for_sprint(db, org_id, sprint_id)


@router.get("/sprints/{sprint_id}/approvals", response_model=list[SprintApprovalResponse])
def api_list_approvals(
    sprint_id: str,
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    return list_approvals_for_sprint(db, org_id, sprint_id)


@router.get("/sprints/{sprint_id}/burndown", response_model=list[BurndownPointOut])
def api_burndown(
    sprint_id: str,
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    return compute_burndown(db, org_id, sprint_id)


# ── Mutations ──────────────────────────────────────────────────────

@router.post("/projects/{project_id}/sprints", response_model=SprintResponse, status_code=201)
def api_create_sprint(
    project_id: str,
    data: SprintCreate,
    request: Request,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Create a new sprint under a project. Index auto-assigned if omitted."""
    ensure_project_access(db, org_id, project_id)
    sp = create_sprint(db, org_id, project_id, data)
    write_audit(
        db, org_id=org_id, actor_id=user_id,
        action="sprint_created",
        entity_type="sprint", entity_id=sp.id,
        meta={"name": sp.name, "project_id": project_id},
        request=request,
    )
    return sp


@router.post("/sprints/{sprint_id}/tasks", response_model=SprintTaskResponse, status_code=201)
def api_create_task(
    sprint_id: str,
    data: SprintTaskCreate,
    request: Request,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Create a task inside a sprint."""
    task = create_task(db, org_id, sprint_id, data)
    write_audit(
        db, org_id=org_id, actor_id=user_id,
        action="sprint_task_created",
        entity_type="sprint_task", entity_id=task.id,
        meta={"title": task.title, "sprint_id": sprint_id},
        request=request,
    )
    return task


@router.patch("/sprint-tasks/{task_id}", response_model=SprintTaskResponse)
def api_patch_task(
    task_id: str,
    data: SprintTaskUpdate,
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    # Currently only status is wired end-to-end; other fields are accepted
    # but only `status` flows to the kanban DnD path.
    if data.status:
        return update_task_status(db, org_id, task_id, data.status)
    from fastapi import HTTPException
    raise HTTPException(status_code=400, detail="No mutable field provided")


@router.post("/sprint-approvals/{approval_id}/decide", response_model=SprintApprovalResponse)
def api_decide_approval(
    approval_id: str,
    data: ApprovalDecision,
    request: Request,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ap = decide_approval(db, org_id, approval_id, data.decision, decided_by=user_id)
    write_audit(
        db, org_id=org_id, actor_id=user_id,
        action=f"sprint_approval_{data.decision}",
        entity_type="sprint_approval", entity_id=approval_id,
        meta={"sprint_id": ap.sprint_id}, request=request,
    )
    return ap


# ── Seed ──────────────────────────────────────────────────────────

@router.post(
    "/projects/{project_id}/sprints/seed",
    response_model=SeedResult,
    status_code=201,
)
def api_seed_sprints(
    project_id: str,
    request: Request,
    user_id: str = Depends(require_permission("admin:llm:write")),
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    """Idempotent seed of the demo Oracle GL → Snowflake sprint dataset.

    Admin-gated. Wipes any prior sprint data for this project, then inserts
    5 sprints, 24 tasks, 3 risks, 4 approvals, 2 releases, 11 mapping
    nodes, 13 edges, 6 agent executions. Useful for client demos + first
    deploys; safe to re-run to reset to a known state.
    """
    ensure_project_access(db, org_id, project_id)
    result = seed_sprints_for_project(db, org_id, project_id)
    write_audit(
        db, org_id=org_id, actor_id=user_id,
        action="sprints_seeded",
        entity_type="project", entity_id=project_id,
        meta={"counts": {k: v for k, v in result.items() if k.endswith("_created")}},
        request=request,
    )
    return result
