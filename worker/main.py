"""Helix Migration Worker — Temporal entrypoint.

Registers both the monolithic `BMADPlanningWorkflow` (single activity wrapping
the full LangGraph) and the per-node `BMADPerNodeWorkflow` (13 BMAD activities
with a signal-driven human approval gate).

Behaviour on Temporal connect failure:
  - `APP_ENV=production`: exit non-zero so Docker restart_policy kicks in.
  - dev/test: log and exit 0 so unit tests don't need Temporal running.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from temporalio.client import Client
from temporalio.worker import Worker

from worker.activities.bmad_activities import execute_bmad_graph_activity
from worker.activities.bmad_node_activities import (
    amelia_code_review_activity,
    amelia_dev_activity,
    amelia_qa_activity,
    amelia_story_activity,
    john_prd_activity,
    mary_analyze_activity,
    paige_docs_activity,
    persist_workflow_step_activity,
    sally_ux_activity,
    winston_architecture_activity,
    winston_project_context_activity,
    winston_readiness_activity,
    winston_stories_activity,
)
from worker.workflows.bmad_per_node_workflow import BMADPerNodeWorkflow
from worker.workflows.bmad_planning_workflow import BMADPlanningWorkflow

logger = logging.getLogger(__name__)

TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "helix-bmad-task-queue")
TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
APP_ENV = os.getenv("APP_ENV", "development")


async def main() -> int:
    """Connect to Temporal and run the worker. Returns process exit code."""
    logger.info("Connecting to Temporal at %s", TEMPORAL_ADDRESS)
    try:
        client = await Client.connect(TEMPORAL_ADDRESS)
        logger.info("Connected to Temporal server")
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to connect to Temporal at %s: %s", TEMPORAL_ADDRESS, exc)
        if APP_ENV == "production":
            # Non-zero exit so Compose / Kubernetes can restart with backoff.
            logger.error("Production worker requires Temporal — exiting non-zero.")
            return 1
        logger.warning(
            "Temporal not available (env=%s) — exiting cleanly so dev/test can proceed.",
            APP_ENV,
        )
        return 0

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[BMADPlanningWorkflow, BMADPerNodeWorkflow],
        activities=[
            execute_bmad_graph_activity,
            winston_project_context_activity,
            mary_analyze_activity,
            john_prd_activity,
            sally_ux_activity,
            winston_architecture_activity,
            winston_stories_activity,
            winston_readiness_activity,
            amelia_story_activity,
            amelia_dev_activity,
            amelia_qa_activity,
            amelia_code_review_activity,
            paige_docs_activity,
            persist_workflow_step_activity,
        ],
    )

    logger.info(
        "Worker started on task queue '%s' (workflows: BMADPlanningWorkflow, BMADPerNodeWorkflow)",
        TASK_QUEUE,
    )
    await worker.run()
    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    sys.exit(asyncio.run(main()))
