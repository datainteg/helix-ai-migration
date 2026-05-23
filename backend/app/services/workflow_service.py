"""Backend workflow service — starts BMAD planning via Temporal with local fallback.

Production: starts BMADPlanningWorkflow through Temporal. Never silently falls back.
Dev/Test: falls back to direct run_bmad_graph when Temporal is unavailable.
"""

from __future__ import annotations

import logging
import os
import uuid

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from agents.bmad.graph import run_bmad_graph
from app.db.session import SessionLocal
from app.models.workflow import WorkflowRun, WorkflowStep

logger = logging.getLogger(__name__)

TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "helix-bmad-task-queue")
APP_ENV = os.getenv("APP_ENV", "development")


def _is_production() -> bool:
    return APP_ENV == "production"


async def _start_temporal_workflow(input_data: dict) -> dict:
    """Start BMADPlanningWorkflow on Temporal. Returns workflow metadata."""
    from temporalio.client import Client

    from worker.workflows.bmad_planning_workflow import BMADPlanningWorkflow

    client = await Client.connect(TEMPORAL_ADDRESS)
    workflow_id = f"bmad-{input_data['project_id']}-{input_data['requirement_id']}"

    handle = await client.start_workflow(
        BMADPlanningWorkflow.run,
        input_data,
        id=workflow_id,
        task_queue=TASK_QUEUE,
    )

    return {
        "workflow_id": workflow_id,
        "run_id": handle.result_run_id,
        "status": "started",
        "mode": "temporal",
    }


def _run_local_fallback(input_data: dict) -> dict:
    """Fallback: execute BMAD graph directly (dev/test only)."""
    result = run_bmad_graph(
        project_id=input_data["project_id"],
        requirement_id=input_data["requirement_id"],
        organization_id=input_data.get("organization_id"),
        requirement_text=input_data.get("requirement_text"),
        approval_decision=input_data.get("approval_decision"),
    )
    workflow_id = f"local-{uuid.uuid4().hex[:12]}"
    return {
        "workflow_id": workflow_id,
        "run_id": workflow_id,
        "status": result.get("status", "completed"),
        "mode": "local_fallback",
        "result": result,
    }


async def start_bmad_planning_workflow(
    project_id: str,
    requirement_id: str,
    organization_id: str | None = None,
    requirement_text: str | None = None,
    db: Session | None = None,
) -> dict:
    """Start the BMAD planning workflow.

    Tries Temporal first. Falls back to local run_bmad_graph only in
    dev/test environments. In production, raises if Temporal is unavailable.

    Args:
        project_id: Project UUID
        requirement_id: Migration requirement UUID
        organization_id: Organization UUID (for scoping)
        requirement_text: Raw requirement text

    Returns:
        Dict with workflow_id, run_id, status, mode
    """
    input_data = {
        "project_id": project_id,
        "requirement_id": requirement_id,
        "organization_id": organization_id,
        "requirement_text": requirement_text,
    }

    # Try Temporal first
    try:
        result = await _start_temporal_workflow(input_data)
        logger.info(
            "BMAD workflow started via Temporal: %s (mode=%s)",
            result["workflow_id"],
            result["mode"],
        )
        _persist_started_workflow(db, result, input_data)
        return result
    except Exception as exc:
        if _is_production():
            logger.error("Temporal unavailable in production: %s", exc)
            raise RuntimeError(
                "Temporal workflow service is unavailable. "
                "BMAD planning cannot proceed without the workflow engine."
            ) from exc

        logger.warning(
            "Temporal unavailable (dev fallback): %s — using local run_bmad_graph",
            exc,
        )

    # Dev/test fallback
    result = _run_local_fallback(input_data)
    logger.info(
        "BMAD workflow completed via local fallback: %s (mode=%s)",
        result["workflow_id"],
        result["mode"],
    )

    # Persist the workflow run and steps
    _persist_workflow_result(db, result, input_data)

    return result


async def get_workflow_status(
    workflow_id: str,
    db: Session | None = None,
) -> dict:
    """Get BMAD workflow status.

    Returns persisted workflow run state when available.
    Does not fake completed status unless data exists.
    """
    if db is None:
        db = SessionLocal()

    try:
        run = db.query(WorkflowRun).filter(WorkflowRun.workflow_id == workflow_id).first()
    except SQLAlchemyError as exc:
        logger.warning("Workflow status persistence lookup failed: %s", exc)
        run = None

    if run:
        return {
            "workflow_id": run.workflow_id or workflow_id,
            "run_id": run.run_id,
            "status": run.status or "unknown",
            "mode": run.mode,
            "project_id": run.project_id,
            "requirement_id": run.requirement_id,
            "organization_id": run.organization_id,
        }

    return {
        "workflow_id": workflow_id,
        "status": "unknown",
        "mode": "temporal" if "bmad-" in workflow_id else "local_fallback",
        "note": "Workflow run not found in persistence.",
    }


def _persist_started_workflow(db: Session | None, result: dict, input_data: dict) -> None:
    """Persist a Temporal-started workflow run as 'started'."""
    own_db = db is None
    if own_db:
        db = SessionLocal()
    try:
        create_workflow_run(
            db,
            organization_id=input_data.get("organization_id", "unknown"),
            project_id=input_data["project_id"],
            requirement_id=input_data["requirement_id"],
            workflow_id=result["workflow_id"],
            run_id=result["run_id"],
            status="started",
            mode="temporal",
        )
    except SQLAlchemyError as exc:
        logger.warning("Failed to persist started workflow: %s", exc)
        db.rollback()
    finally:
        if own_db:
            db.close()


def _persist_workflow_result(db: Session | None, result: dict, input_data: dict) -> None:
    """Persist a completed workflow run and its agent steps."""
    own_db = db is None
    if own_db:
        db = SessionLocal()
    try:
        run = create_workflow_run(
            db,
            organization_id=input_data.get("organization_id", "unknown"),
            project_id=input_data["project_id"],
            requirement_id=input_data["requirement_id"],
            workflow_id=result["workflow_id"],
            run_id=result["run_id"],
            status=result["status"],
            mode=result["mode"],
        )

        agent_outputs = result.get("result", {}).get("outputs", {})
        agent_order = ["business_analyst", "architect", "validation_planner", "approval_gate"]
        for idx, agent_name in enumerate(agent_order):
            if agent_name in agent_outputs:
                save_workflow_step(
                    db,
                    workflow_run_id=run.id,
                    agent_name=agent_name,
                    step_order=str(idx + 1),
                    status="completed",
                    raw_output=str(agent_outputs[agent_name]),
                    parsed_output_json=agent_outputs[agent_name],
                )
    except SQLAlchemyError as exc:
        logger.warning("Failed to persist workflow result: %s", exc)
        db.rollback()
    finally:
        if own_db:
            db.close()


# ── Persistence CRUD (Prompt 10) ──────────────────────────────────────

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
    """Create a new workflow run record."""
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
) -> WorkflowRun | None:
    """Update the status of a workflow run."""
    run = db.query(WorkflowRun).filter(WorkflowRun.workflow_id == workflow_id).first()
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
    step_order: str,
    status: str = "completed",
    raw_output: str | None = None,
    parsed_output_json: dict | None = None,
    provider_name: str | None = None,
    model_name: str | None = None,
    error_message: str | None = None,
) -> WorkflowStep:
    """Save an agent step output within a workflow run."""
    import json

    step = WorkflowStep(
        workflow_run_id=workflow_run_id,
        agent_name=agent_name,
        step_order=step_order,
        status=status,
        raw_output=raw_output,
        parsed_output_json=json.dumps(parsed_output_json) if parsed_output_json else None,
        provider_name=provider_name,
        model_name=model_name,
        error_message=error_message,
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


def get_workflow_run(db: Session, workflow_id: str) -> WorkflowRun | None:
    """Get a workflow run by ID."""
    return db.query(WorkflowRun).filter(WorkflowRun.workflow_id == workflow_id).first()


def list_workflow_runs(db: Session, organization_id: str, project_id: str | None = None) -> list[WorkflowRun]:
    """List workflow runs for an organization, optionally filtered by project."""
    q = db.query(WorkflowRun).filter(WorkflowRun.organization_id == organization_id)
    if project_id:
        q = q.filter(WorkflowRun.project_id == project_id)
    return q.order_by(WorkflowRun.created_at.desc()).all()
