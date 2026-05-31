"""Agent workflow API — start and monitor BMAD planning workflows."""

import asyncio
import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.db.session import get_db
from app.core.config import settings
from app.auth.jwt import get_current_user_id
from app.auth.dependencies import get_current_organization_id, require_permission, user_has_role
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
from app.schemas.pagination import PaginatedResponse, paginate
from app.utils.idempotency import idempotent


class StartWorkflowRequest(BaseModel):
    requirement_id: str
    # SC-019: this text is concatenated into every BMAD agent's LLM prompt;
    # cap at 10 KB so a malicious member cannot burn the org's token budget
    # with a multi-MB requirement.
    requirement_text: str | None = Field(default=None, max_length=10_000)


class StartWorkflowResponse(BaseModel):
    workflow_id: str
    run_id: str
    status: str
    mode: str
    result: dict | None = None  # Full graph output in local_fallback mode


class ApprovalRequest(BaseModel):
    decision: str  # "approved" or "rejected"
    # SC-019: approval notes can flow into downstream prompts / audit meta.
    notes: str = Field(default="", max_length=10_000)


class WorkflowRunSummary(BaseModel):
    """Per-row shape returned by the list endpoints.

    Used as the `T` in `PaginatedResponse[WorkflowRunSummary]` so the
    OpenAPI schema enumerates real fields instead of a bare `dict`.
    The shape mirrors what `_serialize_workflow_runs` produced before.
    `created_at` is an ISO-8601 string (pydantic's default `datetime`
    encoding) rather than the legacy `str(datetime)` repr.
    """

    workflow_id: str
    run_id: str | None = None
    status: str | None = None
    mode: str | None = None
    project_id: str | None = None
    requirement_id: str | None = None
    created_at: str | None = None


class ApprovalSignalResponse(BaseModel):
    """Acknowledgement returned by /approve, /signal-approve, /signal-reject."""

    workflow_id: str
    status: str
    decision: str | None = None
    signal: str | None = None


class WorkflowArtifactRef(BaseModel):
    agent_name: str
    step_order: int
    artifact_path: str


class WorkflowArtifactContent(BaseModel):
    """Artifact file content returned by /artifact-content.

    NOTE: `path` echoes the on-disk path because the existing UI passes it
    back as the lookup key. Path-traversal is blocked by the per-workflow
    allowlist check before this endpoint reads the file.
    """

    path: str
    content: str


router = APIRouter(tags=["agent-workflows"])


def _artifact_canonical_roots() -> list[Path]:
    """SC-014: the set of directories an artifact path is allowed to live
    under. A workflow step row stores `artifact_path` written by the worker
    — if the worker is ever compromised (or prompt-injection persuades it to
    record `/etc/passwd`), the per-workflow allowlist alone would still serve
    the file because the path exists in the row. We additionally pin every
    served path under one of these canonical roots.

    Roots:
      * settings.ARTIFACT_STORAGE_PATH — the backend's local artifact store.
      * the BMAD `_bmad-output` directory — where the worker persists
        planning artifacts (mounted read-only into the backend container).
        Resolved from HELIX_PROJECT_ROOT to mirror worker/main.py.
    """
    roots: list[Path] = []
    try:
        roots.append(Path(settings.ARTIFACT_STORAGE_PATH or "./data/artifacts").resolve())
    except Exception:
        pass
    # BMAD output root. Worker uses HELIX_PROJECT_ROOT (defaults /app in
    # container) and writes under <root>/_bmad-output.
    project_root = os.getenv("HELIX_PROJECT_ROOT") or os.getcwd()
    try:
        roots.append((Path(project_root) / "_bmad-output").resolve())
    except Exception:
        pass
    # Optional explicit override for non-standard deployments.
    override = os.getenv("HELIX_BMAD_OUTPUT_ROOT")
    if override:
        try:
            roots.append(Path(override).resolve())
        except Exception:
            pass
    return roots


def _artifact_path_is_allowed(path: str) -> bool:
    """True iff `path` resolves to a file under one of the canonical roots."""
    try:
        resolved = Path(path).resolve()
    except Exception:
        return False
    for root in _artifact_canonical_roots():
        try:
            if resolved == root or resolved.is_relative_to(root):
                return True
        except (ValueError, AttributeError):
            # is_relative_to raises ValueError on unrelated drives (Windows);
            # AttributeError only on <3.9 (not in scope).
            continue
    return False


@router.post("/projects/{project_id}/agent-workflows", response_model=StartWorkflowResponse)
@idempotent("start_workflow")
async def start_workflow(
    request: Request,
    project_id: str,
    data: StartWorkflowRequest,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Start a BMAD planning workflow for a project requirement.

    Idempotent on `Idempotency-Key` header (API-C4). Network retries with
    the same key + body return the cached response for 24h instead of
    starting a second workflow + paying 2x LLM cost.
    """
    ensure_project_access(db, org_id, project_id)

    # Operational hold — a project on hold refuses new workflow starts.
    from app.models.project import Project as _Project
    _proj = db.query(_Project).filter(_Project.id == project_id).first()
    if _proj is not None and getattr(_proj, "on_hold", False):
        raise HTTPException(status_code=409, detail="Project is on hold — set it live before starting a workflow.")

    # Pre-start approval gate — when the project requires approval, a direct
    # start is refused; runs must go through request → approve.
    if _proj is not None and getattr(_proj, "require_run_approval", True):
        raise HTTPException(
            status_code=409,
            detail="This project requires manager approval before a run can start. Submit a run request instead.",
        )

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


# ── Pre-start approval gate ─────────────────────────────────────────────
def _request_to_dict(r) -> dict:
    return {
        "id": r.id, "project_id": r.project_id, "requirement_id": r.requirement_id,
        "requested_by": r.requested_by, "status": r.status, "approver_id": r.approver_id,
        "notes": r.notes, "workflow_id": r.workflow_id,
        "created_at": str(r.created_at) if r.created_at else None,
    }


@router.post("/projects/{project_id}/agent-workflows/request", status_code=201)
async def request_workflow_run(
    project_id: str,
    data: StartWorkflowRequest,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Submit a run request for manager approval (pre-start gate). Does NOT start
    the workflow — an approver must approve it first."""
    from app.models.project import Project as _Project, WorkflowRunRequest
    ensure_project_access(db, org_id, project_id)
    proj = db.query(_Project).filter(_Project.id == project_id).first()
    if proj is not None and getattr(proj, "on_hold", False):
        raise HTTPException(status_code=409, detail="Project is on hold — set it live before requesting a run.")
    requirement = db.query(MigrationRequirement).filter(
        MigrationRequirement.id == data.requirement_id, MigrationRequirement.project_id == project_id,
    ).first()
    if not requirement:
        raise HTTPException(status_code=404, detail="Requirement not found")

    req = WorkflowRunRequest(
        project_id=project_id, requirement_id=data.requirement_id,
        requested_by=user_id, status="pending",
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return _request_to_dict(req)


@router.get("/projects/{project_id}/run-requests")
def list_run_requests(
    project_id: str,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Run requests for a project (newest first) — drives the approval queue."""
    from app.models.project import WorkflowRunRequest
    ensure_project_access(db, org_id, project_id)
    rows = (
        db.query(WorkflowRunRequest)
        .filter(WorkflowRunRequest.project_id == project_id)
        .order_by(WorkflowRunRequest.created_at.desc())
        .all()
    )
    return [_request_to_dict(r) for r in rows]


class RejectRequest(BaseModel):
    notes: str | None = None


@router.post("/agent-workflows/requests/{request_id}/approve")
async def approve_run_request(
    request: Request,
    request_id: str,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(require_permission("agent:approve")),
    db: Session = Depends(get_db),
):
    """Approve a pending run request and START the workflow. Separation of
    duties: the requester cannot approve their own request."""
    from app.models.project import WorkflowRunRequest
    req = db.query(WorkflowRunRequest).filter(WorkflowRunRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Run request not found")
    ensure_project_access(db, org_id, req.project_id)
    if req.status != "pending":
        raise HTTPException(status_code=409, detail=f"Request already {req.status}.")
    # Separation of duties: a regular approver can't approve their own request.
    # Admins / super-admins may self-approve (they own the project governance).
    if req.requested_by == user_id and not user_has_role(db, user_id, {"super_admin", "admin"}):
        raise HTTPException(status_code=403, detail="You can't approve your own run request (separation of duties).")

    requirement = db.query(MigrationRequirement).filter(MigrationRequirement.id == req.requirement_id).first()
    if not requirement:
        raise HTTPException(status_code=404, detail="Requirement no longer exists")

    correlation_id = getattr(request.state, "request_id", None) if request else None
    result = await start_bmad_planning_workflow(
        project_id=req.project_id, requirement_id=req.requirement_id,
        organization_id=org_id, requirement_text=requirement.source_text,
        db=db, correlation_id=correlation_id,
    )
    req.status = "approved"
    req.approver_id = user_id
    req.workflow_id = result["workflow_id"]
    db.commit()
    db.refresh(req)
    return {**_request_to_dict(req), "run": result}


@router.post("/agent-workflows/requests/{request_id}/reject")
def reject_run_request(
    request_id: str,
    data: RejectRequest,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(require_permission("agent:approve")),
    db: Session = Depends(get_db),
):
    """Reject a pending run request with optional notes."""
    from app.models.project import WorkflowRunRequest
    req = db.query(WorkflowRunRequest).filter(WorkflowRunRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Run request not found")
    ensure_project_access(db, org_id, req.project_id)
    if req.status != "pending":
        raise HTTPException(status_code=409, detail=f"Request already {req.status}.")
    if req.requested_by == user_id and not user_has_role(db, user_id, {"super_admin", "admin"}):
        raise HTTPException(status_code=403, detail="You can't action your own run request (separation of duties).")
    req.status = "rejected"
    req.approver_id = user_id
    req.notes = data.notes
    db.commit()
    db.refresh(req)
    return _request_to_dict(req)


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


@router.get(
    "/agent-workflows/{workflow_id}/artifacts",
    response_model=list[WorkflowArtifactRef],
)
async def list_workflow_artifacts(
    workflow_id: str,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Return every artifact path produced by a workflow's agents."""
    _assert_workflow_in_org(db, workflow_id, org_id)
    status = await get_workflow_status(workflow_id, db=db)
    artifacts: list[WorkflowArtifactRef] = []
    for step in status.get("steps", []):
        if step.get("artifact_path"):
            artifacts.append(
                WorkflowArtifactRef(
                    agent_name=step["agent_name"],
                    step_order=step["step_order"],
                    artifact_path=step["artifact_path"],
                )
            )
    return artifacts


@router.get(
    "/agent-workflows/{workflow_id}/artifact-content",
    response_model=WorkflowArtifactContent,
)
async def read_workflow_artifact(
    workflow_id: str,
    path: str,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Read the raw markdown content of one artifact produced by this workflow.

    Path must match one of the artifact_paths persisted on the workflow's steps
    AND resolve (after symlink/.. canonicalisation) under a pinned BMAD output
    root (SC-014) — guards against arbitrary filesystem reads even if a
    compromised worker records a hostile `artifact_path`.
    """
    _assert_workflow_in_org(db, workflow_id, org_id)
    status = await get_workflow_status(workflow_id, db=db)
    # M-011: canonicalise (realpath) BOTH the stored allowlist entries and the
    # supplied path before comparing, so a symlinked stored path and the
    # client-supplied path resolve to the same absolute target. Builds on the
    # SC-014 canonical-root pin below. We keep an exact-string fallback so a
    # stored path that no longer exists on disk (realpath returns it unchanged)
    # still matches an identical supplied string.
    raw_allowed = {step.get("artifact_path") for step in status.get("steps", [])}
    raw_allowed.discard(None)
    canon_allowed = {os.path.realpath(p) for p in raw_allowed}
    if os.path.realpath(path) not in canon_allowed and path not in raw_allowed:
        raise HTTPException(status_code=403, detail="Path not associated with this workflow")
    # SC-014: hard-pin to canonical roots. Reject anything that escapes the
    # BMAD output / artifact-storage directories after resolving symlinks
    # and `..` segments. Done even though the path is in `allowed_paths`
    # because step rows are populated by the worker, not the user.
    if not _artifact_path_is_allowed(path):
        raise HTTPException(status_code=403, detail="Artifact path outside permitted storage roots")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Artifact file missing on disk")
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    return {"path": path, "content": content}


@router.post(
    "/agent-workflows/{workflow_id}/approve",
    response_model=ApprovalSignalResponse,
)
async def approve_step(
    workflow_id: str,
    data: ApprovalRequest,
    request: Request,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Record a human approval decision for a workflow step.

    H-015: a per-node Temporal workflow blocks in
    `workflow.wait_condition(approval_decision is not None)`. Previously
    /approve only flipped the DB row, leaving Temporal waiting until the 48h
    timeout — the DB said "rejected" while Temporal kept running. We now send
    the matching Temporal signal BEFORE flipping the DB row. If the workflow
    handle can't be resolved (older row predating Temporal, or Temporal down)
    we log a warning and proceed with a DB-only update so the legacy path
    still works.
    """
    _assert_workflow_in_org(db, workflow_id, org_id)

    new_status = "approved" if data.decision == "approved" else "rejected"

    # Best-effort Temporal signal so the waiting workflow actually advances.
    signal_name = "approve" if new_status == "approved" else "reject"
    try:
        from temporalio.client import Client

        client = await Client.connect(os.getenv("TEMPORAL_ADDRESS", "localhost:7233"))
        handle = client.get_workflow_handle(workflow_id)
        await handle.signal(signal_name, data.notes)
    except Exception:  # noqa: BLE001
        # Handle not resolvable (pre-Temporal row) or Temporal unavailable.
        # Proceed with the DB-only update — never echo Temporal internals.
        import logging
        logging.getLogger(__name__).warning(
            "Temporal signal '%s' could not be delivered for workflow %s; "
            "proceeding with DB-only status update.",
            signal_name, workflow_id,
        )

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

    return ApprovalSignalResponse(
        workflow_id=workflow_id,
        decision=data.decision,
        status=new_status,
    )


@router.get("/agent-workflows/{workflow_id}/stream")
async def stream_workflow_progress(
    request: Request,
    workflow_id: str,
    token: str,
):
    """SSE stream of workflow step events.

    Auth via `?token=` query string because the browser EventSource API
    cannot send custom headers. Frontend must mint a 60-second scope=sse
    ticket via POST /auth/sse-ticket and pass it here.

    PERF-2 (REVIEW_PERFORMANCE.md / H-8): does NOT take a
    `Depends(get_db)` session because that would pin one DB
    connection for the full 2-minute polling window. Auth + access
    check run on a short-lived `SessionLocal()` that's closed
    before the generator starts; each loop iteration opens a fresh
    session, runs the status query, and closes the session before
    `asyncio.sleep` — so the pool is held only for the ~ms-long
    query. Each tick also calls `await request.is_disconnected()`
    so a closed browser tab tears the loop down immediately
    instead of running to the 2-min cap.
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
            if payload.get("scope") != "sse":
                raise ValueError("token is not an sse ticket")
            # SC-013: the ticket must be consumed from the same client it was
            # minted for (forwarded IP + UA hash). A leaked ticket replayed
            # from another client fails this check even within its 60s TTL.
            if not sse_ticket_binding_ok(
                token, get_client_ip(request), request.headers.get("user-agent")
            ):
                raise ValueError("sse ticket client mismatch")
            org_id = resolve_active_org_id(auth_db, user_id)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid stream token")

        _assert_workflow_in_org(auth_db, workflow_id, org_id)
    finally:
        auth_db.close()

    # H-003: capture the token's expiry so the stream can self-terminate when
    # the JWT lapses mid-stream instead of continuing to push events for up to
    # 2 minutes with an expired credential.
    token_exp = payload.get("exp")

    def _sse(event_type: str, body: dict) -> str:
        # M-016: emit a typed `event:` line in addition to the `data:` JSON.
        # The JSON still carries `type` so existing `onmessage` consumers keep
        # working; clients that prefer typed dispatch can `addEventListener`
        # on the event name instead.
        return f"event: {event_type}\ndata: {json.dumps(body)}\n\n"

    async def event_generator():
        import time as _time
        last_step_count = 0
        try:
            for tick in range(120):  # max 2 min polling at 1s intervals
                # Tear down immediately when the client goes away.
                if await request.is_disconnected():
                    return

                # H-003: every 10 ticks, re-validate the token. Cheap exp
                # check each cycle; a full re-decode every 10s catches
                # revocation too. On expiry/revocation, emit a final
                # `auth_expired` event and close the stream cleanly so the
                # client knows to re-authenticate rather than silently
                # streaming on an invalid credential.
                if token_exp is not None and _time.time() >= float(token_exp):
                    yield _sse("auth_expired", {"type": "auth_expired"})
                    return
                if tick and tick % 10 == 0:
                    try:
                        await decode_access_token_async(token)
                    except Exception:  # noqa: BLE001
                        yield _sse("auth_expired", {"type": "auth_expired"})
                        return

                # Fresh DB session per tick; closed before the
                # asyncio.sleep so the pool is never held idle.
                tick_db = SessionLocal()
                try:
                    status = await get_workflow_status(workflow_id, db=tick_db)
                finally:
                    tick_db.close()

                steps = status.get("steps", [])
                if len(steps) > last_step_count:
                    for step in steps[last_step_count:]:
                        yield _sse("step", {"type": "step", "step": step})
                    last_step_count = len(steps)

                run_status = status.get("status", "")
                if run_status in ("completed", "approved", "rejected", "failed"):
                    yield _sse("done", {"type": "done", "status": run_status})
                    return

                await asyncio.sleep(1)
            yield _sse("timeout", {"type": "timeout"})
        except asyncio.CancelledError:
            # Client closed the connection mid-yield. Re-raise so
            # Starlette can clean up cancellation without logging an
            # unhandled-exception traceback.
            raise

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/agent-workflows/{workflow_id}/signal-approve",
    response_model=ApprovalSignalResponse,
)
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
        return ApprovalSignalResponse(workflow_id=workflow_id, signal="approve", status="sent")
    except HTTPException:
        raise
    except Exception:
        # Never echo Temporal's raw exception (would expose internal addresses
        # / stack traces to clients). Log + return a generic 503; operators get
        # the full trace from server logs.
        import logging
        logging.getLogger(__name__).exception("Temporal signal failure (approve) for workflow %s", workflow_id)
        raise HTTPException(status_code=503, detail="Workflow signal backend unavailable")


@router.post(
    "/agent-workflows/{workflow_id}/signal-reject",
    response_model=ApprovalSignalResponse,
)
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
        return ApprovalSignalResponse(workflow_id=workflow_id, signal="reject", status="sent")
    except HTTPException:
        raise
    except Exception:
        # Sanitize: never echo Temporal's raw exception to API clients.
        import logging
        logging.getLogger(__name__).exception("Temporal signal failure (reject) for workflow %s", workflow_id)
        raise HTTPException(status_code=503, detail="Workflow signal backend unavailable")


@router.get(
    "/projects/{project_id}/agent-workflows",
    response_model=PaginatedResponse[WorkflowRunSummary],
)
def list_workflows(
    project_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """List workflow runs for a project (paginated envelope)."""
    ensure_project_access(db, org_id, project_id)
    runs = list_workflow_runs(db, organization_id=org_id, project_id=project_id)
    rows = _serialize_workflow_runs(runs)
    # `rows` is the full result set here, so `paginate()` infers total from it.
    return paginate(rows, limit=limit, offset=offset)


@router.get(
    "/agent-workflows",
    response_model=PaginatedResponse[WorkflowRunSummary],
)
def list_all_workflows(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """List every workflow run for the current organization (paginated envelope)."""
    runs = list_workflow_runs(db, organization_id=org_id)
    rows = _serialize_workflow_runs(runs)
    return paginate(rows, limit=limit, offset=offset)


def _serialize_workflow_runs(runs) -> list[WorkflowRunSummary]:
    # Return typed objects so the envelope serializer can document the
    # row shape in OpenAPI. `.isoformat()` produces a real ISO-8601 string
    # (e.g. "2026-05-26T14:33:21+00:00"), replacing the previous
    # `str(datetime)` repr that JS parsers in Safari rejected.
    return [
        WorkflowRunSummary(
            workflow_id=r.workflow_id,
            run_id=r.run_id,
            status=r.status,
            mode=r.mode,
            project_id=r.project_id,
            requirement_id=r.requirement_id,
            created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in runs
    ]
