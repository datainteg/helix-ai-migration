"""Helix Migration Worker — Temporal entrypoint.

Registers both the monolithic `BMADPlanningWorkflow` (single activity wrapping
the full LangGraph) and the per-node `BMADPerNodeWorkflow` (13 BMAD activities
with a signal-driven human approval gate).

Behaviour on Temporal connect failure:
  - `APP_ENV=production`: exit non-zero so Docker restart_policy kicks in.
  - dev/test: log and exit 0 so unit tests don't need Temporal running.

BMAD Artifact Path Contract (W-002):
  - BMAD config specifies: planning_artifacts = "{project-root}/_bmad-output/planning-artifacts"
  - In container with HELIX_PROJECT_ROOT=/app: resolves to /app/_bmad-output/planning-artifacts
  - Docker Compose volume mount: helix_artifacts:/app/_bmad-output
  - These paths must align so artifacts persist across restarts.
  - A runtime assertion verifies the artifact directory is writable at startup.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from datetime import timedelta
from pathlib import Path

from temporalio.client import Client
from temporalio.worker import Worker

from agents.runtime.bmad_loader import load_bmad_config
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


def _verify_bmad_artifact_store() -> bool:
    """Verify that the BMAD artifact directory is writable at startup.

    Returns True if the artifact store is ready, False otherwise.
    Logs clear errors if the check fails.

    W-002 / W-013: This assertion ensures the compose volume mount is correctly
    configured at /app/_bmad-output (or wherever HELIX_PROJECT_ROOT points).
    If the volume fails to mount (e.g. volume name mismatch), this catches it
    before the worker accepts tasks from Temporal.
    """
    try:
        cfg = load_bmad_config()
        planning_root = Path(cfg.planning_artifacts).parent
        planning_root.mkdir(parents=True, exist_ok=True)

        # Attempt a test write to verify the filesystem is writable.
        test_file = planning_root / ".healthcheck"
        test_file.touch()
        test_file.unlink()

        logger.info(
            "BMAD artifact store verified: planning_artifacts=%s, parent=%s (writable)",
            cfg.planning_artifacts,
            planning_root,
        )
        return True
    except OSError as exc:
        logger.error(
            "BMAD artifact directory not writable. Check volume mount at /app/_bmad-output. "
            "Error: %s",
            exc,
        )
        return False
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Failed to verify BMAD artifact store: %s. "
            "This likely indicates a compose volume mount misconfiguration.",
            exc,
        )
        return False


async def main() -> int:
    """Connect to Temporal and run the worker. Returns process exit code."""
    # W-002/W-013: Verify BMAD artifact store before accepting tasks from Temporal.
    # Fail fast if the compose volume mount is misconfigured.
    if not _verify_bmad_artifact_store():
        if APP_ENV == "production":
            logger.error("BMAD artifact store verification failed in production — exiting non-zero.")
            return 1
        logger.warning(
            "BMAD artifact store verification failed (env=%s) — continuing in dev mode.",
            APP_ENV,
        )

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

    # Concurrency cap (W-003): default 5 matches the 3+2 DB pool size.
    # Raise via WORKER_MAX_CONCURRENT_ACTIVITIES env var for larger instances.
    max_concurrent_activities = int(os.getenv("WORKER_MAX_CONCURRENT_ACTIVITIES", "5"))
    max_concurrent_workflows = int(os.getenv("WORKER_MAX_CONCURRENT_WORKFLOWS", "5"))

    # Graceful drain (W-007): give in-flight LLM activities up to 15 min to
    # finish before the worker process exits on SIGTERM.  This prevents
    # Temporal from retrying costly Anthropic/Opus calls that were mid-flight.
    graceful_shutdown_timeout = timedelta(
        minutes=int(os.getenv("WORKER_GRACEFUL_SHUTDOWN_MINUTES", "15"))
    )

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        max_concurrent_activities=max_concurrent_activities,
        max_concurrent_workflow_tasks=max_concurrent_workflows,
        graceful_shutdown_timeout=graceful_shutdown_timeout,
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

    # Install SIGTERM handler so an explicit `docker stop` (or Kubernetes pod
    # eviction) triggers a clean drain rather than killing mid-activity.
    # The handler schedules worker.shutdown() on the running event loop.
    loop = asyncio.get_running_loop()

    def _handle_sigterm() -> None:
        logger.info("SIGTERM received — initiating graceful worker shutdown")
        loop.create_task(worker.shutdown())

    try:
        loop.add_signal_handler(signal.SIGTERM, _handle_sigterm)
    except (NotImplementedError, OSError):
        # Windows does not support add_signal_handler; skip silently.
        pass

    logger.info(
        "Worker started on task queue '%s' "
        "(max_concurrent_activities=%d, max_concurrent_workflows=%d, "
        "graceful_shutdown_timeout=%s) "
        "(workflows: BMADPlanningWorkflow, BMADPerNodeWorkflow)",
        TASK_QUEUE,
        max_concurrent_activities,
        max_concurrent_workflows,
        graceful_shutdown_timeout,
    )
    await worker.run()
    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    sys.exit(asyncio.run(main()))
