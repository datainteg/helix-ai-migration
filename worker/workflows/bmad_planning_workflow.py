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

# Activity reference lives outside the sandbox; imports_passed_through tells
# Temporal not to try to re-import this module inside the workflow sandbox.
with workflow.unsafe.imports_passed_through():
    from worker.activities.bmad_activities import execute_bmad_graph_activity

logger = logging.getLogger(__name__)


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

        result = await workflow.execute_activity(
            execute_bmad_graph_activity,
            input_data,
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=5),
                maximum_attempts=3,
                backoff_coefficient=2.0,
            ),
        )

        logger.info(
            "BMAD workflow completed: id=%s status=%s",
            workflow_id,
            result.get("status"),
        )
        return result
