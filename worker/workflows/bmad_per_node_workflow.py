"""BMAD per-node Temporal workflow.

Mirrors the 13-node LangGraph pipeline but executes each BMAD step as a
separate Temporal activity. Each activity gets its own retry policy + timeout.
Human approval is signal-driven via `workflow.wait_condition()`.

Sequence (matches `agents/bmad/graph.py`):

  Phase 0:  winston_project_context
  Phase 1:  mary_analyze
  Phase 2:  john_prd, sally_ux
  Phase 3:  winston_architecture, winston_stories, winston_readiness
  ──────── approval signal (approve / reject) ────────
  Phase 4:  amelia_story, amelia_dev, amelia_qa, amelia_code_review
  Phase 5:  paige_docs

Public introspection:
  - `current_step` query → returns the step currently in-flight (for live UIs
    that don't want to poll the WorkflowStep DB table).
  - `outputs` query → returns the accumulated per-agent parsed metadata.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

# Activity imports live outside the workflow sandbox.
with workflow.unsafe.imports_passed_through():
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

logger = logging.getLogger(__name__)

_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    maximum_attempts=3,
    backoff_coefficient=2.0,
)
_ACTIVITY_TIMEOUT = timedelta(minutes=10)
_PERSIST_TIMEOUT = timedelta(seconds=30)
_APPROVAL_TIMEOUT = timedelta(hours=48)


@workflow.defn
class BMADPerNodeWorkflow:
    """Per-node BMAD migration workflow with human approval signal."""

    def __init__(self) -> None:
        self._approval_decision: str | None = None
        self._approval_notes: str = ""
        self._current_step: str = "init"
        self._outputs: dict[str, Any] = {}
        self._artifact_paths: dict[str, list[str]] = {}

    # ── Signals ────────────────────────────────────────────────────

    @workflow.signal
    def approve(self, notes: str = "") -> None:
        self._approval_decision = "approved"
        self._approval_notes = notes

    @workflow.signal
    def reject(self, notes: str = "") -> None:
        self._approval_decision = "rejected"
        self._approval_notes = notes

    # ── Queries ────────────────────────────────────────────────────

    @workflow.query
    def current_step(self) -> str:
        return self._current_step

    @workflow.query
    def outputs(self) -> dict[str, Any]:
        return self._outputs

    @workflow.query
    def artifact_paths(self) -> dict[str, list[str]]:
        return self._artifact_paths

    # ── Run ────────────────────────────────────────────────────────

    @workflow.run
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        workflow_id = workflow.info().workflow_id
        run_id = input_data.get("workflow_run_id", workflow_id)

        async def run_step(fn, agent_key: str, step_order: int) -> dict[str, Any]:
            self._current_step = agent_key
            result = await workflow.execute_activity(
                fn,
                input_data,
                start_to_close_timeout=_ACTIVITY_TIMEOUT,
                retry_policy=_RETRY,
            )
            await workflow.execute_activity(
                persist_workflow_step_activity,
                {
                    "workflow_run_id": run_id,
                    "agent_name": agent_key,
                    "step_order": step_order,
                    "status": "completed" if result.get("success") else "failed",
                    "parsed": result.get("parsed"),
                    "artifact_path": result.get("artifact_path"),
                    "mode": result.get("mode"),
                    "errors": result.get("errors", []),
                },
                start_to_close_timeout=_PERSIST_TIMEOUT,
                retry_policy=_RETRY,
            )
            if result.get("artifact_path"):
                agent_code = result.get("agent")
                if agent_code:
                    self._artifact_paths.setdefault(agent_code, []).append(result["artifact_path"])
            return result

        # Phase 0: shared-memory bootstrap.
        self._outputs["project_context"] = (
            await run_step(winston_project_context_activity, "project_context", 1)
        )["parsed"]

        # Phase 1: analysis.
        self._outputs["analyst"] = (await run_step(mary_analyze_activity, "analyst", 2))["parsed"]

        # Phase 2: planning.
        self._outputs["pm"] = (await run_step(john_prd_activity, "pm", 3))["parsed"]
        self._outputs["ux_designer"] = (await run_step(sally_ux_activity, "ux_designer", 4))["parsed"]

        # Phase 3: solutioning.
        self._outputs["architect"] = (await run_step(winston_architecture_activity, "architect", 5))["parsed"]
        self._outputs["architect_stories"] = (
            await run_step(winston_stories_activity, "architect_stories", 6)
        )["parsed"]
        self._outputs["architect_readiness"] = (
            await run_step(winston_readiness_activity, "architect_readiness", 7)
        )["parsed"]

        # Approval gate (signal-driven).
        self._current_step = "awaiting_approval"
        logger.info("BMAD per-node waiting for approval signal: %s", workflow_id)
        await workflow.wait_condition(
            lambda: self._approval_decision is not None,
            timeout=_APPROVAL_TIMEOUT,
        )

        if self._approval_decision != "approved":
            self._current_step = "rejected"
            return {
                "workflow_id": workflow_id,
                "status": "rejected",
                "outputs": self._outputs,
                "artifact_paths": self._artifact_paths,
                "approval_notes": self._approval_notes,
            }

        # Phase 4: implementation.
        self._outputs["dev_story"] = (await run_step(amelia_story_activity, "dev_story", 8))["parsed"]
        self._outputs["dev"] = (await run_step(amelia_dev_activity, "dev", 9))["parsed"]
        self._outputs["qa"] = (await run_step(amelia_qa_activity, "qa", 10))["parsed"]
        self._outputs["code_review"] = (await run_step(amelia_code_review_activity, "code_review", 11))["parsed"]

        # Phase 5: docs.
        self._outputs["tech_writer"] = (await run_step(paige_docs_activity, "tech_writer", 12))["parsed"]

        self._current_step = "completed"
        return {
            "workflow_id": workflow_id,
            "status": "completed",
            "outputs": self._outputs,
            "artifact_paths": self._artifact_paths,
            "approval_notes": self._approval_notes,
        }
