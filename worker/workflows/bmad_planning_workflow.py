"""Temporal workflow for BMAD migration planning (monolithic mode).

Workflow code MUST be deterministic — no I/O, no random, no datetime, no
external service calls. Everything external runs inside activities.

The activity is referenced as a function (not by string name) so the
Temporal sandbox can validate types + serialization at registration time.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

# Activity references live outside the sandbox; imports_passed_through tells
# Temporal not to try to re-import this module inside the workflow sandbox.
with workflow.unsafe.imports_passed_through():
    from worker.activities.bmad_activities import execute_bmad_graph_activity
    from worker.activities.bmad_node_activities import (
        persist_workflow_terminal_state_activity,
    )

logger = logging.getLogger(__name__)

_PERSIST_TIMEOUT = timedelta(seconds=30)
_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    maximum_attempts=3,
    backoff_coefficient=2.0,
)


@workflow.defn
class BMADPlanningWorkflow:
    """Durable BMAD planning workflow executed by Temporal.

    Invokes the BMAD LangGraph as a single activity with retry + timeout.

    Workflow ID convention: bmad-{project_id}-{requirement_id}
    """

    @workflow.run
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        workflow_id = workflow.info().workflow_id
        logger.info("BMAD workflow started: id=%s", workflow_id)

        async def reconcile_terminal_state(status: str, summary: dict | None = None) -> None:
            """Flip the WorkflowRun row to the terminal status (C-002).

            Mirrors ``BMADPerNodeWorkflow.reconcile_terminal_state``: the
            persist activity has its own retry policy and swallows DB errors,
            so a transient DB hiccup never blocks the workflow's own terminal
            state. Without this the monolithic path leaves WorkflowRun stuck
            at ``status="started"`` and the SSE stream times out at 120s on
            every successful run.
            """
            try:
                await workflow.execute_activity(
                    persist_workflow_terminal_state_activity,
                    {
                        "workflow_id": workflow_id,
                        "status": status,
                        "summary": summary,
                    },
                    start_to_close_timeout=_PERSIST_TIMEOUT,
                    retry_policy=_RETRY,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Terminal-state reconcile activity failed for %s (status=%s): %s",
                    workflow_id,
                    status,
                    exc,
                )

        try:
            result = await workflow.execute_activity(
                execute_bmad_graph_activity,
                input_data,
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=_RETRY,
            )

            logger.info(
                "BMAD workflow completed: id=%s status=%s",
                workflow_id,
                result.get("status"),
            )
            await reconcile_terminal_state("completed")
            return result
        except Exception as exc:
            # The graph activity exhausted its retries (or another unhandled
            # failure occurred). Mark the DB row "failed" before letting
            # Temporal propagate the failure so the SSE stream + dashboard see
            # the terminal state without a manual reconcile.
            logger.exception(
                "BMAD workflow failed: workflow_id=%s err=%s",
                workflow_id,
                exc,
            )
            await reconcile_terminal_state(
                "failed",
                summary={"error": str(exc)[:500]},
            )
            raise
