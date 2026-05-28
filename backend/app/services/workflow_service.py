"""Backend workflow service — wraps `HelixBMAD` for FastAPI routes.

Single import point: `from agents import HelixBMAD`. This file translates
between HTTP-shaped inputs/outputs and the HelixBMAD class API, and persists
results to the WorkflowRun + WorkflowStep tables.

Production: starts the Temporal-backed workflow via `HelixBMAD.start_temporal()`.
Dev/test: falls back to `HelixBMAD.run()` (in-process LangGraph) when Temporal
is unavailable.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from agents import HelixBMAD, HelixBMADResult
from app.db.session import SessionLocal
from app.models.workflow import WorkflowRun, WorkflowStep

logger = logging.getLogger(__name__)

APP_ENV = os.getenv("APP_ENV", "development")


def _is_production() -> bool:
    return APP_ENV == "production"


async def start_bmad_planning_workflow(
    project_id: str,
    requirement_id: str,
    organization_id: str | None = None,
    requirement_text: str | None = None,
    db: Session | None = None,
    correlation_id: str | None = None,
    prompt_overrides: dict[str, str] | None = None,
) -> dict:
    """Start the BMAD planning workflow via Temporal, with a dev-only local fallback.

    `correlation_id` should be the request's X-Request-ID header (injected by
    `RequestIdMiddleware`) so the trace propagates from HTTP → workflow →
    activity → executor → artifact frontmatter → Prometheus metrics.

    Returns a dict shaped like `HelixBMADResult.to_dict()` plus `result` for the
    local-fallback case (which carries the full LangGraph state).
    """
    # Cost guardrail — refuse start when the org has breached its USD cap in
    # hard-enforcement mode. Soft mode logs but allows.
    if organization_id and db is not None:
        try:
            from app.services.cost_service import check_within_cap
            allowed, reason = check_within_cap(db, organization_id)
            if not allowed:
                raise RuntimeError(f"Cost cap exceeded for org {organization_id}: {reason}")
            if reason:
                logger.warning("Cost cap soft-breach for org=%s: %s", organization_id, reason)
        except RuntimeError:
            raise
        except Exception as exc:  # noqa: BLE001
            # Failing the cap lookup must not block legit workflows; log + continue.
            logger.warning("Cost cap check failed; allowing workflow: %s", exc)

    helix = HelixBMAD(
        project_id=project_id,
        requirement_id=requirement_id,
        organization_id=organization_id,
        requirement_text=requirement_text or "",
        correlation_id=correlation_id,
        prompt_overrides=prompt_overrides,
    )

    # Try Temporal first.
    try:
        started = await helix.start_temporal()
        logger.info(
            "BMAD workflow started via Temporal: %s (run_id=%s)",
            started.workflow_id,
            started.run_id,
        )
        _persist_started_workflow(db, started, helix)
        return started.to_dict()
    except Exception as exc:  # noqa: BLE001
        if _is_production():
            logger.error("Temporal unavailable in production: %s", exc)
            raise RuntimeError(
                "Temporal workflow service is unavailable. "
                "BMAD planning cannot proceed without the workflow engine."
            ) from exc
        logger.warning(
            "Temporal unavailable (dev fallback): %s — using local HelixBMAD.run()",
            exc,
        )

    # Dev/test fallback — run the graph in-process. Off-loaded to a worker
    # thread so the FastAPI event loop does not block on the synchronous
    # LangGraph state-machine (which itself makes blocking LLM HTTP calls).
    result = await asyncio.to_thread(helix.run)
    # Local runs get a synthetic workflow_id distinct from the Temporal one.
    result.workflow_id = f"local-{uuid.uuid4().hex[:12]}"
    result.run_id = result.workflow_id
    result.mode = "local_fallback"
    logger.info(
        "BMAD workflow completed via local fallback: %s (status=%s)",
        result.workflow_id,
        result.status,
    )

    _persist_workflow_result(db, result, helix)
    payload = result.to_dict()
    payload["result"] = {
        "outputs": result.outputs,
        "artifact_paths": result.artifact_paths,
        "final_output": result.final_output,
        "approval_required": result.status == "pending",
    }
    return payload


async def get_workflow_status(
    workflow_id: str,
    db: Session | None = None,
) -> dict:
    """Lookup workflow status from the persisted WorkflowRun row.

    Returns the run header + every persisted step (agent name, status, parsed_output,
    artifact path). Frontend uses this to render the 13-node BMAD pipeline view.
    """
    if db is None:
        db = SessionLocal()

    try:
        run = db.query(WorkflowRun).filter(WorkflowRun.workflow_id == workflow_id).first()
    except SQLAlchemyError as exc:
        logger.warning("Workflow status persistence lookup failed: %s", exc)
        run = None

    if not run:
        return {
            "workflow_id": workflow_id,
            "status": "unknown",
            "mode": "temporal" if "bmad-" in workflow_id else "local_fallback",
            "note": "Workflow run not found in persistence.",
            "steps": [],
        }

    steps_raw = (
        db.query(WorkflowStep)
        .filter(WorkflowStep.workflow_run_id == run.id)
        .order_by(WorkflowStep.step_order)
        .all()
    )
    steps = []
    for s in steps_raw:
        artifact_path: str | None = None
        if s.raw_output:
            try:
                payload = json.loads(s.raw_output)
                paths = payload.get("artifact_paths") or payload.get("artifact_path")
                if isinstance(paths, list) and paths:
                    artifact_path = paths[-1]
                elif isinstance(paths, str):
                    artifact_path = paths
            except (json.JSONDecodeError, AttributeError):
                pass
        steps.append({
            "agent_name": s.agent_name,
            "step_order": s.step_order,
            "status": s.status,
            "parsed_output": s.parsed_output_json,
            "artifact_path": artifact_path,
            "provider_name": s.provider_name,
            "model_name": s.model_name,
            "error_message": s.error_message,
            "created_at": str(s.created_at) if s.created_at else None,
        })

    return {
        "workflow_id": run.workflow_id or workflow_id,
        "run_id": run.run_id,
        "status": run.status or "unknown",
        "mode": run.mode,
        "project_id": run.project_id,
        "requirement_id": run.requirement_id,
        "organization_id": run.organization_id,
        "created_at": str(run.created_at) if run.created_at else None,
        "steps": steps,
    }


# ── Persistence ──────────────────────────────────────────────────────


def _persist_started_workflow(db: Session | None, started: HelixBMADResult, helix: HelixBMAD) -> None:
    own_db = db is None
    if own_db:
        db = SessionLocal()
    try:
        create_workflow_run(
            db,
            organization_id=helix.organization_id or "unknown",
            project_id=helix.project_id,
            requirement_id=helix.requirement_id,
            workflow_id=started.workflow_id,
            run_id=started.run_id,
            status="started",
            mode="temporal",
        )
    except SQLAlchemyError as exc:
        logger.warning("Failed to persist started workflow: %s", exc)
        db.rollback()
    finally:
        if own_db:
            db.close()


def _upsert_workflow_run(
    db: Session,
    *,
    organization_id: str,
    project_id: str,
    requirement_id: str,
    workflow_id: str,
    run_id: str,
    status: str,
    mode: str,
) -> WorkflowRun:
    """C-001: insert-or-update a workflow_run keyed by (workflow_id, org).

    The Temporal path inserts a `status="started"` row in
    `_persist_started_workflow`; later (and on the local-fallback path) we must
    NOT insert a second row with the same workflow_id — that produced duplicate
    rows and, once the unique index lands, an IntegrityError. Select the
    existing row FOR UPDATE (serialising concurrent writers for the same
    workflow) and update it, otherwise insert.
    """
    q = db.query(WorkflowRun).filter(
        WorkflowRun.workflow_id == workflow_id,
        WorkflowRun.organization_id == organization_id,
    )
    # FOR UPDATE only on backends that support row locks (Postgres). SQLite
    # ignores it; the test path is single-writer anyway.
    try:
        if db.bind is not None and db.bind.dialect.name == "postgresql":
            q = q.with_for_update()
    except Exception:  # noqa: BLE001
        pass
    existing = q.first()
    if existing:
        existing.status = status
        existing.mode = mode
        if run_id:
            existing.run_id = run_id
        db.commit()
        db.refresh(existing)
        return existing
    return create_workflow_run(
        db,
        organization_id=organization_id,
        project_id=project_id,
        requirement_id=requirement_id,
        workflow_id=workflow_id,
        run_id=run_id,
        status=status,
        mode=mode,
    )


def _persist_workflow_result(db: Session | None, result: HelixBMADResult, helix: HelixBMAD) -> None:
    own_db = db is None
    if own_db:
        db = SessionLocal()
    try:
        # C-001: upsert so a pre-existing "started" row (Temporal path) is
        # updated in place rather than duplicated. Steps are persisted against
        # the resolved run's id below.
        run = _upsert_workflow_run(
            db,
            organization_id=helix.organization_id or "unknown",
            project_id=helix.project_id,
            requirement_id=helix.requirement_id,
            workflow_id=result.workflow_id,
            run_id=result.run_id,
            status=result.status,
            mode=result.mode,
        )

        agent_order = [
            "project_context",
            "analyst",
            "pm",
            "ux_designer",
            "architect",
            "architect_stories",
            "architect_readiness",
            "approval_gate",
            "dev_story",
            "dev",
            "qa",
            "code_review",
            "tech_writer",
        ]
        # Map output_key → producing BMAD agent_code so step rows can look up
        # the artifact frontmatter for provider/model provenance.
        output_key_to_agent_code = {
            "project_context": "bmad-agent-architect",
            "analyst": "bmad-agent-analyst",
            "pm": "bmad-agent-pm",
            "ux_designer": "bmad-agent-ux-designer",
            "architect": "bmad-agent-architect",
            "architect_stories": "bmad-agent-architect",
            "architect_readiness": "bmad-agent-architect",
            "dev_story": "bmad-agent-dev",
            "dev": "bmad-agent-dev",
            "qa": "bmad-agent-dev",
            "code_review": "bmad-agent-dev",
            "tech_writer": "bmad-agent-tech-writer",
        }
        for idx, agent_name in enumerate(agent_order):
            if agent_name in result.outputs:
                payload = result.outputs[agent_name]
                agent_code = output_key_to_agent_code.get(agent_name)
                paths_for_agent = result.artifact_paths.get(agent_code or agent_name, [])
                # Best-effort: read provider_name (llm_mode) + model_name from
                # the artifact's YAML frontmatter. Failures are non-fatal.
                provider_name: str | None = None
                model_name: str | None = None
                if paths_for_agent:
                    try:
                        import yaml as _yaml
                        with open(paths_for_agent[-1], "r", encoding="utf-8") as f:
                            head = f.read(4096)
                        if head.startswith("---"):
                            parts = head.split("---", 2)
                            if len(parts) >= 3:
                                front = _yaml.safe_load(parts[1]) or {}
                                provider_name = front.get("llm_mode")
                                model_name = front.get("model") or front.get("model_name")
                    except Exception:  # noqa: BLE001 — provenance is best-effort
                        pass
                save_workflow_step(
                    db,
                    workflow_run_id=run.id,
                    agent_name=agent_name,
                    step_order=idx + 1,
                    status="completed",
                    raw_output=json.dumps(
                        {**payload, "artifact_paths": paths_for_agent}
                    ),
                    parsed_output_json=payload,
                    provider_name=provider_name,
                    model_name=model_name,
                )
    except SQLAlchemyError as exc:
        logger.warning("Failed to persist workflow result: %s", exc)
        db.rollback()
    finally:
        if own_db:
            db.close()


# ── CRUD ─────────────────────────────────────────────────────────────


def create_workflow_run(
    db: Session,
    *,
    organization_id: str,
    project_id: str,
    requirement_id: str,
    workflow_id: str,
    run_id: str,
    status: str = "pending",
    mode: str = "local_fallback",
) -> WorkflowRun:
    run = WorkflowRun(
        organization_id=organization_id,
        project_id=project_id,
        requirement_id=requirement_id,
        workflow_id=workflow_id,
        run_id=run_id,
        status=status,
        mode=mode,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def update_workflow_run_status(
    db: Session,
    workflow_id: str,
    status: str,
    organization_id: str | None = None,
) -> WorkflowRun | None:
    """Update a workflow run's status. Pass `organization_id` to enforce
    tenant isolation — when set, a workflow from another org is treated as
    not found (silent no-op + returns None) instead of being mutated."""
    q = db.query(WorkflowRun).filter(WorkflowRun.workflow_id == workflow_id)
    if organization_id is not None:
        q = q.filter(WorkflowRun.organization_id == organization_id)
    run = q.first()
    if run:
        run.status = status
        db.commit()
        db.refresh(run)
    return run


def update_workflow_run_status_for_temporal_completion(
    workflow_id: str,
    status: str,
    summary: str | None = None,
    organization_id: str | None = None,
    db: Session | None = None,
) -> WorkflowRun | None:
    """C-002: reconcile a WorkflowRun to its terminal state when a Temporal
    workflow finishes.

    The worker owns the actual call site (e.g. at the end of
    BMADPerNodeWorkflow.run, via the same persist-step activity wiring that
    already imports this module). Exposing it here keeps the run-status write
    path in one place: the worker calls this with the resolved
    `(workflow_id, status)` and an optional human-readable `summary`, and the
    backend updates the row using its own session when one isn't supplied.

    Returns the updated run, or None if no matching row exists (older
    pre-Temporal rows). Never raises on a missing row so the worker activity
    stays idempotent.
    """
    own_db = db is None
    if own_db:
        db = SessionLocal()
    try:
        q = db.query(WorkflowRun).filter(WorkflowRun.workflow_id == workflow_id)
        if organization_id is not None:
            q = q.filter(WorkflowRun.organization_id == organization_id)
        run = q.first()
        if not run:
            logger.warning(
                "Temporal completion reconcile: no WorkflowRun for workflow_id=%s",
                workflow_id,
            )
            return None
        run.status = status
        # Persist the summary as a terminal step row so the SSE stream and the
        # status endpoint surface it without a schema change to WorkflowRun.
        if summary:
            try:
                save_workflow_step(
                    db,
                    workflow_run_id=run.id,
                    agent_name="_terminal",
                    step_order=9999,
                    status=status,
                    error_message=None if status != "failed" else summary[:2000],
                    parsed_output_json={"summary": summary[:8000]},
                )
            except SQLAlchemyError as exc:
                logger.warning("Failed to persist terminal summary step: %s", exc)
                db.rollback()
        db.commit()
        db.refresh(run)
        return run
    finally:
        if own_db:
            db.close()


def save_workflow_step(
    db: Session,
    *,
    workflow_run_id: str,
    agent_name: str,
    step_order: int,
    status: str = "completed",
    raw_output: str | None = None,
    parsed_output_json: dict | None = None,
    provider_name: str | None = None,
    model_name: str | None = None,
    error_message: str | None = None,
) -> WorkflowStep:
    step = WorkflowStep(
        workflow_run_id=workflow_run_id,
        agent_name=agent_name,
        step_order=step_order,
        status=status,
        raw_output=raw_output,
        parsed_output_json=parsed_output_json,
        provider_name=provider_name,
        model_name=model_name,
        error_message=error_message,
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


def get_workflow_run(
    db: Session,
    workflow_id: str,
    organization_id: str | None = None,
) -> WorkflowRun | None:
    """Load a workflow run by id. Pass `organization_id` to scope the lookup
    to a single tenant — recommended for all API-layer callers."""
    q = db.query(WorkflowRun).filter(WorkflowRun.workflow_id == workflow_id)
    if organization_id is not None:
        q = q.filter(WorkflowRun.organization_id == organization_id)
    return q.first()


def list_workflow_runs(db: Session, organization_id: str, project_id: str | None = None) -> list[WorkflowRun]:
    q = db.query(WorkflowRun).filter(WorkflowRun.organization_id == organization_id)
    if project_id:
        q = q.filter(WorkflowRun.project_id == project_id)
    return q.order_by(WorkflowRun.created_at.desc()).all()
