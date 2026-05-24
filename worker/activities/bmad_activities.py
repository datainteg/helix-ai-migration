"""Temporal activity wrapping the BMAD LangGraph (monolithic mode).

`run_bmad_graph` is synchronous (file I/O + subprocess calls + blocking HTTP),
so this activity is defined as `def` (sync). Temporal runs sync activities in
a thread pool, which is correct for blocking workloads.
"""

from __future__ import annotations

import logging
from typing import Any

from temporalio import activity

from agents.bmad.graph import run_bmad_graph

logger = logging.getLogger(__name__)


@activity.defn
def execute_bmad_graph_activity(input_data: dict[str, Any]) -> dict[str, Any]:
    """Execute the BMAD LangGraph planning workflow.

    Single Temporal activity that wraps the entire 13-node BMAD graph.

    Args:
        input_data: Dict with keys: project_id, requirement_id, organization_id,
                    requirement_text, approval_decision.

    Returns:
        Final state dict from `run_bmad_graph` — includes outputs, artifact_paths,
        status, errors, final_output.
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
        if activity.in_activity():
            activity.heartbeat("bmad_graph_completed")

        logger.info(
            "BMAD activity completed: status=%s agents=%d",
            result.get("status"),
            len(result.get("outputs", {})),
        )
        return result
    except Exception as exc:
        logger.error("BMAD activity failed: %s", exc)
        raise
