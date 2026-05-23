"""Helix Migration Worker — Temporal worker entrypoint.

Starts a Temporal worker on the helix-bmad-task-queue, registering
the BMADPlanningWorkflow and execute_bmad_graph_activity.
"""

from __future__ import annotations

import asyncio
import logging
import os

from temporalio.client import Client
from temporalio.worker import Worker

from worker.activities.bmad_activities import execute_bmad_graph_activity
from worker.workflows.bmad_planning_workflow import BMADPlanningWorkflow

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "helix-bmad-task-queue")
TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")


async def main():
    """Connect to Temporal and start the worker."""
    logger.info("Connecting to Temporal at %s", TEMPORAL_ADDRESS)

    try:
        client = await Client.connect(TEMPORAL_ADDRESS)
        logger.info("Connected to Temporal server")
    except Exception as exc:
        logger.error("Failed to connect to Temporal at %s: %s", TEMPORAL_ADDRESS, exc)
        logger.warning(
            "Temporal is not available. In production this is fatal; "
            "in dev/test the backend workflow service falls back to "
            "local run_bmad_graph instead."
        )
        return

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[BMADPlanningWorkflow],
        activities=[execute_bmad_graph_activity],
    )

    logger.info("Worker started on task queue '%s'", TASK_QUEUE)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
