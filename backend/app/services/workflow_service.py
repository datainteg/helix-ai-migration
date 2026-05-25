"""Backend workflow service — wraps `HelixBMAD` for FastAPI routes.

Single import point: `from agents import HelixBMAD`. This file translates
between HTTP-shaped inputs/outputs and the HelixBMAD class API, and persists
results to the WorkflowRun + WorkflowStep tables.

Production: starts the Temporal-backed workflow via `HelixBMAD.start_temporal()`.
Dev/test: falls back to `HelixBMAD.run()` (in-process LangGraph) when Temporal
is unavailable.
"""

from __future__ import annotations

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
) -> dict:
    """Start the BMAD planning workflow via Temporal, with a dev-only local fallback.

    `correlation_id` should be the request's X-Request-ID header (injected by
    `RequestIdMiddleware`) so the trace propagates from HTTP → workflow →
    activity → executor → artifact frontmatter → Prometheus metrics.

    Returns a dict shaped like `HelixBMADResult.to_dict()` plus `result` for the
    local-fallback case (which carries the full LangGraph state).
    """
    helix = HelixBMAD(
        project_id=project_id,
        requirement_id=requirement_id,
        organization_id=organization_id,
        requirement_text=requirement_text or "",
        correlation_id=correlation_id,
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

    # Dev/test fallback — run the graph in-process.
    result = helix.run()
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


def _persist_workflow_result(db: Session | None, result: HelixBMADResult, helix: HelixBMAD) -> None:
    own_db = db is None
    if own_db:
        db = SessionLocal()
    try:
        run = create_workflow_run(
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
