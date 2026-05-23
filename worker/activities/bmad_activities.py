"""Temporal activities for BMAD workflow execution.

All external I/O (graph execution, LLM calls) runs inside activities
to keep workflow code deterministic.
"""

from __future__ import annotations

import logging
from typing import Any

from temporalio import activity

from agents.bmad.graph import run_bmad_graph

logger = logging.getLogger(__name__)


@activity.defn
async def execute_bmad_graph_activity(input_data: dict[str, Any]) -> dict[str, Any]:
    """Execute the BMAD LangGraph planning workflow.

    This is the single Temporal activity that wraps the entire BMAD graph.
    It calls `run_bmad_graph` with the input_data parameters.

    Args:
        input_data: Dict with keys: project_id, requirement_id, organization_id,
                    requirement_text, approval_decision

    Returns:
        Serialized workflow result dict with outputs, status, errors
    """
    logger.info(
        "BMAD activity started: project=%s requirement=%s",
        input_data.get("project_id"),
        input_data.get("requirement_id"),
    )

    try:
        result = run_bmad_graph(
            project_id=input_data["project_id"],
            requirement_id=input_data["requirement_id"],
            organization_id=input_data.get("organization_id"),
            requirement_text=input_data.get("requirement_text"),
            approval_decision=input_data.get("approval_decision"),
        )
        try:
            activity.heartbeat("bmad_graph_completed")
        except RuntimeError:
            pass  # Not in activity context (unit test without Temporal server)

        logger.info(
            "BMAD activity completed: status=%s agents=%d",
            result.get("status"),
            len(result.get("outputs", {})),
        )
        return result
    except Exception as exc:
        logger.error("BMAD activity failed: %s", exc)
        raise
