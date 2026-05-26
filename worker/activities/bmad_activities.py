"""Temporal activity wrapping the BMAD LangGraph (monolithic mode).

`run_bmad_graph` is synchronous (file I/O + subprocess calls + blocking HTTP),
so this activity is defined as `def` (sync). Temporal runs sync activities in
a thread pool, which is correct for blocking workloads.

Heartbeat strategy
------------------
Per-node activities (bmad_node_activities.py) use `_run_with_heartbeats`, which
runs the work in a sub-thread and heartbeats every HEARTBEAT_INTERVAL_SEC (10 s)
from the activity thread.

This monolithic activity uses the same helper — re-imported from bmad_node_activities
— so Temporal never sees a silent activity for 10-15 min and marks it dead
(W-005 fix).  The pattern is:

  _run_with_heartbeats(fn, detail_prefix)
    └─ submits fn() to a ThreadPoolExecutor
    └─ polls future.result(timeout=10s) in a loop
    └─ heartbeats on each timeout until fn() returns
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
    Heartbeats are emitted every 10 s while the graph runs so Temporal does
    not kill this long-running activity on heartbeat_timeout (W-005).

    Args:
        input_data: Dict with keys: project_id, requirement_id, organization_id,
                    requirement_text, approval_decision.

    Returns:
        Final state dict from `run_bmad_graph` — includes outputs, artifact_paths,
        status, errors, final_output.
    """
    # Import the shared heartbeat helper from per-node activities.
    # It is defined as a plain function (not an activity) so importing it here
    # introduces no circular dependency.
    from worker.activities.bmad_node_activities import _run_with_heartbeats

    logger.info(
        "BMAD monolithic activity started: project=%s requirement=%s",
        input_data.get("project_id"),
        input_data.get("requirement_id"),
    )

    try:
        result = _run_with_heartbeats(
            lambda: run_bmad_graph(
                project_id=input_data["project_id"],
                requirement_id=input_data["requirement_id"],
                organization_id=input_data.get("organization_id"),
                requirement_text=input_data.get("requirement_text"),
                approval_decision=input_data.get("approval_decision"),
            ),
            detail_prefix="bmad_graph",
        )

        logger.info(
            "BMAD monolithic activity completed: status=%s agents=%d",
            result.get("status"),
            len(result.get("outputs", {})),
        )
        return result
    except Exception as exc:
        logger.error("BMAD monolithic activity failed: %s", exc)
        raise
