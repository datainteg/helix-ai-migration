"""Backend workflow service — starts BMAD planning via Temporal with local fallback.

Production: starts BMADPlanningWorkflow through Temporal. Never silently falls back.
Dev/Test: falls back to direct run_bmad_graph when Temporal is unavailable.
"""

from __future__ import annotations

import logging
import os
import uuid

from agents.bmad.graph import run_bmad_graph

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
    return result


async def get_workflow_status(workflow_id: str) -> dict:
    """Get BMAD workflow status.

    For MVP, returns a placeholder with TODO note if no persistence exists.
    Does not fake completed status unless data exists.

    Args:
        workflow_id: Temporal workflow ID or local fallback ID

    Returns:
        Dict with workflow_id, status, and metadata.
    """
    # TODO: Query workflow_runs table once Prompt 10 (persistence) is implemented.
    # For now, return a clear placeholder.
    return {
        "workflow_id": workflow_id,
        "status": "unknown",
        "mode": "temporal" if "bmad-" in workflow_id else "local_fallback",
        "note": "Workflow persistence not yet implemented. See Prompt 10.",
    }
