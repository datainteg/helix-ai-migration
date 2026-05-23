"""BMAD per-node Temporal workflow with signal-based human approval.

Each BMAD agent runs as a separate activity. After the Validation Planner,
the workflow pauses and waits for an 'approve' or 'reject' signal before
proceeding to the PM summary activity.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

logger = logging.getLogger(__name__)

_ACTIVITY_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    maximum_attempts=3,
    backoff_coefficient=2.0,
)

_ACTIVITY_TIMEOUT = timedelta(minutes=5)
_APPROVAL_TIMEOUT = timedelta(hours=48)


@workflow.defn
class BMADPerNodeWorkflow:
    """BMAD workflow where each agent is a separate Temporal activity.

    Signals:
      - approve(notes: str): approve the plan and continue to PM summary
      - reject(notes: str): reject the plan; workflow ends with 'rejected' status
    """

    def __init__(self) -> None:
        self._approval_decision: str | None = None
        self._approval_notes: str = ""

    @workflow.signal
    def approve(self, notes: str = "") -> None:
        self._approval_decision = "approved"
        self._approval_notes = notes

    @workflow.signal
    def reject(self, notes: str = "") -> None:
        self._approval_decision = "rejected"
        self._approval_notes = notes

    @workflow.run
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        from worker.activities.bmad_node_activities import (
            run_business_analyst_activity,
            run_architect_activity,
            run_validation_planner_activity,
            run_pm_activity,
            persist_workflow_step_activity,
        )

        workflow_id = workflow.info().workflow_id
        run_id = input_data.get("workflow_run_id", workflow_id)
        outputs: dict[str, Any] = {}

        async def run_node(fn, step_order: int) -> dict[str, Any]:
            result = await workflow.execute_activity(
                fn,
                input_data,
                start_to_close_timeout=_ACTIVITY_TIMEOUT,
                retry_policy=_ACTIVITY_RETRY,
            )
            await workflow.execute_activity(
                persist_workflow_step_activity,
                {
                    "workflow_run_id": run_id,
                    "agent_name": result["agent"],
                    "step_order": step_order,
                    "status": result["status"],
                    "output": result["output"],
                },
                start_to_close_timeout=timedelta(seconds=30),
            )
            return result

        ba = await run_node(run_business_analyst_activity, 1)
        outputs["business_analyst"] = ba["output"]

        arch = await run_node(run_architect_activity, 2)
        outputs["architect"] = arch["output"]

        vp = await run_node(run_validation_planner_activity, 3)
        outputs["validation_planner"] = vp["output"]

        # Wait for human approval signal
        logger.info("BMAD waiting for approval signal: %s", workflow_id)
        await workflow.wait_condition(
            lambda: self._approval_decision is not None,
            timeout=_APPROVAL_TIMEOUT,
        )

        if self._approval_decision != "approved":
            return {
                "workflow_id": workflow_id,
                "status": "rejected",
                "outputs": outputs,
                "approval_notes": self._approval_notes,
            }

        pm = await run_node(run_pm_activity, 4)
        outputs["pm"] = pm["output"]

        return {
            "workflow_id": workflow_id,
            "status": "completed",
            "outputs": outputs,
            "approval_notes": self._approval_notes,
        }
