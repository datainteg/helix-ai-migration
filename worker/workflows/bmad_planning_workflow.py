"""Temporal workflow for BMAD migration planning.

Workflow code MUST be deterministic — no direct I/O, random, datetime,
or external service calls. All external operations run inside activities.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

logger = logging.getLogger(__name__)


@workflow.defn
class BMADPlanningWorkflow:
    """Durable BMAD planning workflow executed by Temporal.

    Invokes the execute_bmad_graph_activity with retry and timeout.
    The activity wraps the LangGraph StateGraph (BA → Architect → VP → Approval).

    Workflow ID format: bmad-{project_id}-{requirement_id}
    """

    @workflow.run
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute the BMAD planning workflow.

        Args:
            input_data: Dict with project_id, requirement_id, organization_id,
                        requirement_text, approval_decision.

        Returns:
            Dict with workflow outputs, status, and metadata.
        """
        workflow_id = workflow.info().workflow_id
        logger.info("BMAD workflow started: id=%s", workflow_id)

        # Activity call — the ONLY external operation in this workflow.
        # Retry policy: max 3 attempts with initial 5s interval.
        result = await workflow.execute_activity(
            "execute_bmad_graph_activity",
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
