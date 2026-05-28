"""Sprint Management API.

Read-mostly: every page in the frontend has a corresponding GET endpoint
keyed off `project_id`. Mutations cover status updates + approval
decisions + the seed trigger. Org scope is enforced by
`ensure_project_access` at the route boundary and by the org filter
inside every service call.
"""

import asyncio
import json
from fastapi import APIRouter, Depends, Query, Request
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
from app.schemas.pagination import PaginatedResponse, paginate
from app.api.audit import write_audit
from app.utils.idempotency import idempotent


router = APIRouter(tags=["sprints"])


# ── Project-scoped lists ────────────────────────────────────────────

@router.get(
    "/projects/{project_id}/sprints",
    response_model=PaginatedResponse[SprintResponse],
)
def api_list_sprints(
    project_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    """List sprints for a project (paginated envelope).

    Breaking change vs v0.x: response is now `{items,total,limit,offset}`
    instead of a bare array. See REVIEW_API_CONTRACT.md §API-C2.
    """
    ensure_project_access(db, org_id, project_id)
    rows = list_sprints(db, org_id, project_id)
    return paginate(rows, limit=limit, offset=offset)


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
    limit: int = Query(50, ge=1, le=200),
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    """List agent executions for a project. Hard-capped at 200 rows to
    align with the standard pagination cap used elsewhere."""
    ensure_project_access(db, org_id, project_id)
    return list_executions(db, org_id, project_id, limit=limit)


@router.get("/projects/{project_id}/sprints/executions/stream")
async def api_executions_stream(
    request: Request,
    project_id: str,
    token: str,
):
    """SSE stream of agent executions. Auth via `?token=` query param
    because the browser EventSource API can't send custom headers — JWT
    is decoded inline below, then the same org-scope check applies.

    Pushes a snapshot frame every 2s with the latest 50 executions.
    Connection auto-closes after 5 minutes; EventSource auto-reconnects
    on the client by default.

    PERF-2 (REVIEW_PERFORMANCE.md / H-8): the handler does NOT take
    a `Depends(get_db)` session — that would pin one DB connection
    to the request for the full 5-minute window. Instead we open a
    short-lived `SessionLocal()` for auth + access check, close it,
    then open a fresh session for every poll tick inside the
    generator and close it before sleeping. Each tick also calls
    `await request.is_disconnected()` so a closed browser tab tears
    the loop down immediately rather than running to the 5-min cap.
    """
    from app.auth.jwt import decode_access_token_async, sse_ticket_binding_ok
    from app.auth.dependencies import resolve_active_org_id
    from app.utils.client_ip import get_client_ip
    from app.db.session import SessionLocal

    # ── Auth + access check on a short-lived session ────────────────
    auth_db = SessionLocal()
    try:
        try:
            payload = await decode_access_token_async(token)
            user_id = payload.get("sub")
            if not user_id:
                raise ValueError("missing sub")
            # Reject full-power tokens used in URLs. Frontend must trade
            # them via POST /auth/sse-ticket which returns a scope=sse
            # short-TTL ticket.
            if payload.get("scope") != "sse":
                raise ValueError("token is not an sse ticket")
            # SC-013: bind-check the ticket to the consuming client (forwarded
            # IP + UA hash). A ticket leaked via proxy/Referer log can't be
            # replayed from another client even inside its 60s TTL.
            if not sse_ticket_binding_ok(
                token, get_client_ip(request), request.headers.get("user-agent")
            ):
                raise ValueError("sse ticket client mismatch")
            org_id = resolve_active_org_id(auth_db, user_id)
        except Exception:
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="Invalid stream token")

        ensure_project_access(auth_db, org_id, project_id)
    finally:
        auth_db.close()

    # H-003: capture token expiry so the stream self-terminates when the
    # JWT lapses mid-stream rather than streaming for the full 5 minutes
    # on an expired credential.
    token_exp = payload.get("exp")

    async def event_generator():
        import time as _time
        seen_ids: set[str] = set()
        # ~150 iterations * 2s = 5 minutes max
        try:
            for tick in range(150):
                # Tear down immediately when the client goes away.
                if await request.is_disconnected():
                    return

                # H-003: re-validate the token. exp check every cycle; a full
                # re-decode every 5 ticks (~10s) also catches revocation. On
                # failure emit `auth_expired` and close cleanly.
                if token_exp is not None and _time.time() >= float(token_exp):
                    yield f"data: {json.dumps({'type': 'auth_expired'})}\n\n"
                    return
                if tick and tick % 5 == 0:
                    try:
                        await decode_access_token_async(token)
                    except Exception:  # noqa: BLE001
                        yield f"data: {json.dumps({'type': 'auth_expired'})}\n\n"
                        return

                # Open a fresh DB session per tick so we never hold a
                # pooled connection across `asyncio.sleep`. Always
                # close in finally — even on yield-cancellation when
                # the client disconnects mid-stream.
                tick_db = SessionLocal()
                try:
                    rows = list_executions(tick_db, org_id, project_id, limit=50)
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
                finally:
                    tick_db.close()

                yield f"data: {json.dumps(payload)}\n\n"
                await asyncio.sleep(2)
            yield f"data: {json.dumps({'type': 'timeout'})}\n\n"
        except asyncio.CancelledError:
            # Client closed the connection mid-yield. Re-raise so
            # Starlette can clean up the response without logging an
            # unhandled exception.
            raise

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


@router.get(
    "/sprints/{sprint_id}/tasks",
    response_model=PaginatedResponse[SprintTaskResponse],
)
def api_list_tasks(
    sprint_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
):
    """List tasks for a sprint (paginated envelope).

    Breaking change vs v0.x: response is now `{items,total,limit,offset}`
    instead of a bare array. See REVIEW_API_CONTRACT.md §API-C2.
    """
    rows = list_tasks_for_sprint(db, org_id, sprint_id)
    return paginate(rows, limit=limit, offset=offset)


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
@idempotent("create_sprint", status_code=201)
async def api_create_sprint(
    project_id: str,
    data: SprintCreate,
    request: Request,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Create a new sprint under a project. Index auto-assigned if omitted.

    Idempotent on `Idempotency-Key` header (API-C4) so retries from a flaky
    network don't insert duplicate sprint rows.
    """
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
@idempotent("create_sprint_task", status_code=201)
async def api_create_task(
    sprint_id: str,
    data: SprintTaskCreate,
    request: Request,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Create a task inside a sprint.

    Idempotent on `Idempotency-Key` header (API-C4).
    """
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
    request: Request,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    # Currently only status is wired end-to-end; other fields are accepted
    # but only `status` flows to the kanban DnD path.
    if not data.status:
        from fastapi import HTTPException
        # 422 (semantic validation) matches FastAPI's body-validation
        # convention better than the previous 400.
        raise HTTPException(
            status_code=422,
            detail="status is the only mutable field currently wired; provide a status value or use the kanban DnD endpoint",
        )
    task = update_task_status(db, org_id, task_id, data.status)
    write_audit(
        db, org_id=org_id, actor_id=user_id,
        action="sprint_task_status_updated",
        entity_type="sprint_task", entity_id=task_id,
        meta={"new_status": data.status},
        request=request,
    )
    return task


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
