"""DB-migration per-node Temporal workflow.

Runs ALONGSIDE the BMAD pipeline on the same worker + task queue. A separate
@workflow.defn type, so Temporal dispatch never crosses the two. 4 nodes vs
BMAD's 13, with the same single human-approval gate — placed AFTER the
TypeMapper so a reviewer signs off the proposed type mapping before any DDL or
data-migration SQL is generated.

  step 1  SchemaAnalyst    (deterministic introspection)
  step 2  TypeMapper       (LLM mapping)
  ──────── approval signal (approve / reject), 48h ────────
  step 3  ScriptGenerator  (LLM + templates)
  step 4  Reconciler       (deterministic recon)

Persistence + terminal-state reconcile reuse the BMAD node activities verbatim
(they key on workflow_run_id/step_order/workflow_id and are agent-name agnostic).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

with workflow.unsafe.imports_passed_through():
    from worker.activities.bmad_node_activities import (
        persist_workflow_step_activity,
        persist_workflow_terminal_state_activity,
    )
    from worker.activities.migration_node_activities import (
        reconciler_activity,
        schema_analyst_activity,
        script_generator_activity,
        type_mapper_activity,
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
class MigrationPerNodeWorkflow:
    """Per-node DB-migration workflow with a human approval gate after mapping."""

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

        async def reconcile_terminal_state(status: str, summary: dict | None = None) -> None:
            try:
                await workflow.execute_activity(
                    persist_workflow_terminal_state_activity,
                    {"workflow_id": workflow_id, "status": status, "summary": summary},
                    start_to_close_timeout=_PERSIST_TIMEOUT,
                    retry_policy=_RETRY,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Migration terminal-state reconcile failed for %s (status=%s): %s",
                    workflow_id, status, exc,
                )

        async def run_step(fn, agent_key: str, step_order: int) -> dict[str, Any]:
            self._current_step = agent_key
            result = await workflow.execute_activity(
                fn,
                input_data,
                start_to_close_timeout=_ACTIVITY_TIMEOUT,
                heartbeat_timeout=timedelta(seconds=60),
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
                bucket = f"{step_order:02d}:{agent_key}"
                self._artifact_paths.setdefault(bucket, []).append(result["artifact_path"])
            if not result.get("success"):
                errors = result.get("errors", []) or []
                msg = f"Migration step {agent_key} (#{step_order}) returned success=False"
                if errors:
                    msg = f"{msg}: {'; '.join(str(e) for e in errors)[:300]}"
                raise ApplicationError(msg, non_retryable=True)
            return result

        try:
            # Phase 1: introspect source schema.
            self._outputs["schema_analyst"] = (
                await run_step(schema_analyst_activity, "schema_analyst", 1)
            )["parsed"]

            # Phase 2: propose type mapping.
            self._outputs["type_mapper"] = (
                await run_step(type_mapper_activity, "type_mapper", 2)
            )["parsed"]

            # Approval gate — reviewer signs off the mapping before any SQL.
            self._current_step = "awaiting_approval"
            logger.info("Migration per-node waiting for approval signal: %s", workflow_id)
            try:
                await workflow.wait_condition(
                    lambda: self._approval_decision is not None,
                    timeout=_APPROVAL_TIMEOUT,
                )
            except asyncio.TimeoutError:
                self._current_step = "expired"
                logger.info("Migration per-node approval expired: %s", workflow_id)
                await reconcile_terminal_state("expired")
                return {
                    "workflow_id": workflow_id, "status": "expired",
                    "outputs": self._outputs, "artifact_paths": self._artifact_paths,
                    "approval_notes": self._approval_notes,
                }

            if self._approval_decision != "approved":
                self._current_step = "rejected"
                await reconcile_terminal_state(
                    "rejected",
                    summary={"approval_notes": self._approval_notes} if self._approval_notes else None,
                )
                return {
                    "workflow_id": workflow_id, "status": "rejected",
                    "outputs": self._outputs, "artifact_paths": self._artifact_paths,
                    "approval_notes": self._approval_notes,
                }

            # Phase 3: generate migration scripts.
            self._outputs["script_generator"] = (
                await run_step(script_generator_activity, "script_generator", 3)
            )["parsed"]

            # Phase 4: reconcile.
            self._outputs["reconciler"] = (
                await run_step(reconciler_activity, "reconciler", 4)
            )["parsed"]

            self._current_step = "completed"
            await reconcile_terminal_state("completed")
            return {
                "workflow_id": workflow_id, "status": "completed",
                "outputs": self._outputs, "artifact_paths": self._artifact_paths,
                "approval_notes": self._approval_notes,
            }
        except Exception as exc:
            self._current_step = "failed"
            logger.exception(
                "Migration per-node workflow failed: workflow_id=%s err=%s", workflow_id, exc,
            )
            await reconcile_terminal_state("failed", summary={"error": str(exc)[:500]})
            raise
