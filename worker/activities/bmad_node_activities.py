"""Per-node Temporal activities for the BMAD migration pipeline.

Each activity wraps one BMAD agent + task skill, executed via
`agents.runtime.bmad_executor.execute_agent_skill`. Activities are thin —
they handle Temporal heartbeats; the BMAD work happens in the executor and
artifact store.

Important — sync vs async:
  `execute_agent_skill` is synchronous (subprocess calls, file I/O, blocking
  HTTP via httpx). To avoid blocking the Temporal worker's event loop we
  define activities as plain `def` (sync). Temporal runs sync activities in a
  thread pool automatically.

Persistence (`persist_workflow_step_activity`) opens a sync SQLAlchemy
SessionLocal — also defined as sync `def` for the same reason.

Workflow-side concerns:
  Activities take explicit `upstream_agents` + `artifact_filename` parameters
  rather than mutating a shared `input_data` dict. Temporal serializes activity
  args by deepcopy on the boundary, but mutating dicts in activities was
  brittle (later activities would see prior activities' mutations if the same
  dict was reused in workflow code).
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout
from typing import Any

from temporalio import activity

logger = logging.getLogger(__name__)


# M-019: a single module-level ThreadPoolExecutor shared across all activity
# invocations instead of constructing (and tearing down) a fresh one-worker
# pool inside every _run_with_heartbeats call. Under load — N concurrent
# activities each spawning + joining their own pool — the per-call pattern
# churned threads and added scheduling latency on every BMAD step. The shared
# pool is sized to the worker's activity concurrency (default 5, matching
# main.py's WORKER_MAX_CONCURRENT_ACTIVITIES) so every in-flight activity
# still gets its own worker thread to run the blocking BMAD work in while the
# activity thread stays awake to heartbeat. A small headroom (+2) covers the
# brief overlap between an activity completing and the next being scheduled.
def _pool_max_workers() -> int:
    try:
        concurrent = int(os.getenv("WORKER_MAX_CONCURRENT_ACTIVITIES", "5"))
    except ValueError:
        concurrent = 5
    return max(concurrent, 1) + 2


_HEARTBEAT_POOL: ThreadPoolExecutor | None = None
_HEARTBEAT_POOL_LOCK = threading.Lock()


def _heartbeat_pool() -> ThreadPoolExecutor:
    """Lazily build + return the shared heartbeat ThreadPoolExecutor."""
    global _HEARTBEAT_POOL
    if _HEARTBEAT_POOL is None:
        with _HEARTBEAT_POOL_LOCK:
            if _HEARTBEAT_POOL is None:
                _HEARTBEAT_POOL = ThreadPoolExecutor(
                    max_workers=_pool_max_workers(),
                    thread_name_prefix="helix-act",
                )
    return _HEARTBEAT_POOL


@atexit.register
def _shutdown_heartbeat_pool() -> None:
    """Best-effort drain of the shared pool on interpreter exit."""
    global _HEARTBEAT_POOL
    if _HEARTBEAT_POOL is not None:
        _HEARTBEAT_POOL.shutdown(wait=False)
        _HEARTBEAT_POOL = None


def _execute(
    agent_code: str,
    skill_name: str,
    output_model_name: str,
    input_data: dict[str, Any],
    upstream_agents: list[str] | None = None,
    artifact_filename: str | None = None,
) -> dict[str, Any]:
    """Resolve output model by name and run an agent+skill (synchronous).

    The agent call is run in a worker thread + periodic heartbeats are
    emitted from the activity thread every HEARTBEAT_INTERVAL_SEC seconds
    so Temporal does not kill long Anthropic/Opus runs (which can take
    >60s) on heartbeat_timeout.
    """
    from agents.bmad import schemas as bmad_schemas
    from agents.runtime.bmad_executor import execute_agent_skill

    output_model = getattr(bmad_schemas, output_model_name)

    result = _run_with_heartbeats(
        lambda: execute_agent_skill(
            agent_code=agent_code,
            skill_name=skill_name,
            project_id=input_data.get("project_id", "unknown"),
            requirement_text=input_data.get("requirement_text", "") or "",
            output_model=output_model,
            upstream_agents=upstream_agents or [],
            org_id=input_data.get("organization_id"),
            artifact_filename=artifact_filename,
            correlation_id=input_data.get("correlation_id"),
        ),
        detail_prefix=f"{agent_code}:{skill_name}",
    )
    return {
        "agent": agent_code,
        "skill": skill_name,
        "success": result.success,
        "mode": result.mode,
        "errors": result.errors,
        "artifact_path": str(result.artifact.path) if result.artifact else None,
        "parsed": result.parsed.model_dump() if result.parsed else None,
    }


HEARTBEAT_INTERVAL_SEC = 10.0

# Heartbeat strategy (shared across monolithic + per-node activities)
# ─────────────────────────────────────────────────────────────────────
# All BMAD activities — both per-node (defined here) and the monolithic
# `execute_bmad_graph_activity` in bmad_activities.py — use _run_with_heartbeats
# to emit a Temporal heartbeat every HEARTBEAT_INTERVAL_SEC (10 s).
#
# Why: LLM calls (Anthropic Opus, OpenAI) regularly exceed 60 s.  Temporal's
# default activity heartbeat_timeout is 10 min, but a monolithic 13-node graph
# can run 10-15 min.  Without periodic heartbeats Temporal marks the activity
# dead and retries, wasting LLM quota and doubling latency.
#
# How: _run_with_heartbeats() submits the blocking work to a ThreadPoolExecutor
# (max_workers=1) and polls future.result(timeout=HEARTBEAT_INTERVAL_SEC) in
# the Temporal activity thread.  On each timeout it calls activity.heartbeat().
# When the work finishes, future.result() returns immediately and the function
# exits.  This approach is safe for sync (`def`) activities because Temporal
# already runs them in its own thread pool — the inner ThreadPoolExecutor adds
# one more hop so the activity thread can stay awake for heartbeats.
#
# Per-node activities: each @activity.defn here calls _run_with_heartbeats via
# _execute(), which wraps execute_agent_skill (one BMAD agent + skill).
#
# Monolithic activity: bmad_activities.execute_bmad_graph_activity imports
# _run_with_heartbeats directly and wraps run_bmad_graph() (entire LangGraph).


def _run_with_heartbeats(fn, detail_prefix: str):
    """Execute `fn()` while heartbeating every HEARTBEAT_INTERVAL_SEC.

    The work runs in a worker thread; the calling thread (the Temporal
    activity thread) blocks on `future.result(timeout=interval)` so it
    wakes up every interval to emit a heartbeat. Without this an LLM call
    that takes >60s exceeds Temporal's default activity heartbeat_timeout
    and the entire workflow step fails + retries.

    M-019: submits to the module-level shared `_HEARTBEAT_POOL` rather than
    spinning up + tearing down a one-worker pool on every call.
    """
    if not activity.in_activity():
        # Outside Temporal (unit tests, manual run) — just call directly.
        return fn()

    seq = 0
    future = _heartbeat_pool().submit(fn)
    while True:
        try:
            return future.result(timeout=HEARTBEAT_INTERVAL_SEC)
        except FutTimeout:
            seq += 1
            _safe_heartbeat(f"{detail_prefix}#{seq}")


def _safe_heartbeat(detail: str) -> None:
    """Heartbeat only when running inside a real activity context."""
    try:
        if activity.in_activity():
            activity.heartbeat(detail)
    except RuntimeError:
        # Not running inside an activity context (unit tests without a worker).
        pass


# ── Phase 0 ──────────────────────────────────────────────────────────


@activity.defn
def winston_project_context_activity(input_data: dict[str, Any]) -> dict[str, Any]:
    _safe_heartbeat("project_context_started")
    result = _execute(
        "bmad-agent-architect",
        "bmad-generate-project-context",
        "ArchitectOutput",
        input_data,
        upstream_agents=[],
        artifact_filename="project-context",
    )
    _safe_heartbeat("project_context_completed")
    logger.info(
        "Winston project_context project=%s mode=%s",
        input_data.get("project_id"),
        result["mode"],
    )
    return result


# ── Phase 1 ──────────────────────────────────────────────────────────


@activity.defn
def mary_analyze_activity(input_data: dict[str, Any]) -> dict[str, Any]:
    _safe_heartbeat("mary_started")
    result = _execute(
        "bmad-agent-analyst",
        "bmad-product-brief",
        "AnalystOutput",
        input_data,
        upstream_agents=["bmad-agent-architect"],
        artifact_filename="product-brief",
    )
    _safe_heartbeat("mary_completed")
    return result


# ── Phase 2 ──────────────────────────────────────────────────────────


@activity.defn
def john_prd_activity(input_data: dict[str, Any]) -> dict[str, Any]:
    _safe_heartbeat("john_started")
    result = _execute(
        "bmad-agent-pm",
        "bmad-prd",
        "PMOutput",
        input_data,
        upstream_agents=["bmad-agent-architect", "bmad-agent-analyst"],
        artifact_filename="prd",
    )
    _safe_heartbeat("john_completed")
    return result


@activity.defn
def sally_ux_activity(input_data: dict[str, Any]) -> dict[str, Any]:
    _safe_heartbeat("sally_started")
    result = _execute(
        "bmad-agent-ux-designer",
        "bmad-create-ux-design",
        "UXDesignerOutput",
        input_data,
        upstream_agents=["bmad-agent-analyst", "bmad-agent-pm"],
        artifact_filename="ux-design",
    )
    _safe_heartbeat("sally_completed")
    return result


# ── Phase 3 ──────────────────────────────────────────────────────────


@activity.defn
def winston_architecture_activity(input_data: dict[str, Any]) -> dict[str, Any]:
    _safe_heartbeat("winston_arch_started")
    result = _execute(
        "bmad-agent-architect",
        "bmad-create-architecture",
        "ArchitectOutput",
        input_data,
        upstream_agents=["bmad-agent-analyst", "bmad-agent-pm", "bmad-agent-ux-designer"],
        artifact_filename="architecture",
    )
    _safe_heartbeat("winston_arch_completed")
    return result


@activity.defn
def winston_stories_activity(input_data: dict[str, Any]) -> dict[str, Any]:
    _safe_heartbeat("winston_stories_started")
    result = _execute(
        "bmad-agent-architect",
        "bmad-create-epics-and-stories",
        "ArchitectOutput",
        input_data,
        upstream_agents=["bmad-agent-analyst", "bmad-agent-pm", "bmad-agent-architect"],
        artifact_filename="epics-and-stories",
    )
    _safe_heartbeat("winston_stories_completed")
    return result


@activity.defn
def winston_readiness_activity(input_data: dict[str, Any]) -> dict[str, Any]:
    _safe_heartbeat("winston_readiness_started")
    result = _execute(
        "bmad-agent-architect",
        "bmad-check-implementation-readiness",
        "ArchitectOutput",
        input_data,
        upstream_agents=[
            "bmad-agent-analyst",
            "bmad-agent-pm",
            "bmad-agent-ux-designer",
            "bmad-agent-architect",
        ],
        artifact_filename="implementation-readiness",
    )
    _safe_heartbeat("winston_readiness_completed")
    return result


# ── Phase 4 ──────────────────────────────────────────────────────────


@activity.defn
def amelia_story_activity(input_data: dict[str, Any]) -> dict[str, Any]:
    _safe_heartbeat("amelia_story_started")
    result = _execute(
        "bmad-agent-dev",
        "bmad-create-story",
        "DevOutput",
        input_data,
        upstream_agents=["bmad-agent-analyst", "bmad-agent-pm", "bmad-agent-architect"],
        artifact_filename="story",
    )
    _safe_heartbeat("amelia_story_completed")
    return result


@activity.defn
def amelia_dev_activity(input_data: dict[str, Any]) -> dict[str, Any]:
    _safe_heartbeat("amelia_dev_started")
    result = _execute(
        "bmad-agent-dev",
        "bmad-dev-story",
        "DevOutput",
        input_data,
        upstream_agents=[
            "bmad-agent-analyst",
            "bmad-agent-pm",
            "bmad-agent-architect",
            "bmad-agent-dev",
        ],
        artifact_filename="dev-implementation",
    )
    _safe_heartbeat("amelia_dev_completed")
    return result


@activity.defn
def amelia_qa_activity(input_data: dict[str, Any]) -> dict[str, Any]:
    _safe_heartbeat("amelia_qa_started")
    result = _execute(
        "bmad-agent-dev",
        "bmad-qa-generate-e2e-tests",
        "QAOutput",
        input_data,
        upstream_agents=["bmad-agent-dev"],
        artifact_filename="qa-tests",
    )
    _safe_heartbeat("amelia_qa_completed")
    return result


@activity.defn
def amelia_code_review_activity(input_data: dict[str, Any]) -> dict[str, Any]:
    _safe_heartbeat("amelia_review_started")
    result = _execute(
        "bmad-agent-dev",
        "bmad-code-review",
        "CodeReviewOutput",
        input_data,
        upstream_agents=["bmad-agent-dev"],
        artifact_filename="code-review",
    )
    _safe_heartbeat("amelia_review_completed")
    return result


# ── Phase 5 ──────────────────────────────────────────────────────────


@activity.defn
def paige_docs_activity(input_data: dict[str, Any]) -> dict[str, Any]:
    _safe_heartbeat("paige_started")
    result = _execute(
        "bmad-agent-tech-writer",
        "bmad-document-project",
        "TechWriterOutput",
        input_data,
        upstream_agents=[
            "bmad-agent-analyst",
            "bmad-agent-pm",
            "bmad-agent-architect",
            "bmad-agent-dev",
        ],
        artifact_filename="migration-docs",
    )
    _safe_heartbeat("paige_completed")
    return result


# ── Persistence ──────────────────────────────────────────────────────


@activity.defn
def persist_workflow_step_activity(step_data: dict[str, Any]) -> None:
    """Persist an agent step + artifact path to the workflow_steps table.

    Idempotent: upserts on (workflow_run_id, step_order) so Temporal activity
    retries do not insert duplicate rows. The unique constraint is enforced
    by alembic migration l3m4n5o6p7q8.

    Uses worker-local SessionLocal (worker/db/session.py) — no backend
    package coupling beyond the shared model class.
    """
    from worker.db.session import SessionLocal
    from app.models.workflow import WorkflowStep

    db = SessionLocal()
    try:
        parsed = step_data.get("parsed") or {}
        raw_output = json.dumps({**parsed, "artifact_path": step_data.get("artifact_path")})
        error_message = "; ".join(step_data.get("errors", [])) or None

        existing = (
            db.query(WorkflowStep)
            .filter(
                WorkflowStep.workflow_run_id == step_data["workflow_run_id"],
                WorkflowStep.step_order == step_data["step_order"],
            )
            .first()
        )
        if existing:
            existing.agent_name = step_data["agent_name"]
            existing.status = step_data.get("status", "completed")
            existing.raw_output = raw_output
            existing.parsed_output_json = parsed
            existing.provider_name = step_data.get("mode")
            existing.model_name = step_data.get("model_name")
            existing.error_message = error_message
        else:
            db.add(WorkflowStep(
                workflow_run_id=step_data["workflow_run_id"],
                agent_name=step_data["agent_name"],
                step_order=step_data["step_order"],
                status=step_data.get("status", "completed"),
                raw_output=raw_output,
                parsed_output_json=parsed,
                provider_name=step_data.get("mode"),
                model_name=step_data.get("model_name"),
                error_message=error_message,
            ))
        db.commit()
    finally:
        db.close()


@activity.defn
def persist_workflow_terminal_state_activity(state_data: dict[str, Any]) -> None:
    """Reconcile the WorkflowRun row's terminal status (C-002).

    Closes the gap where `_persist_started_workflow` writes ``status="started"``
    and nothing ever flips that row to ``completed/failed/rejected/expired``
    once Temporal finishes. The SSE stream in agent_workflows.py polls for
    these terminal statuses; without this activity the stream just times out
    at 120s on every successful run and cost rollups by status are wrong.

    Called from BMADPerNodeWorkflow.run at every exit point (normal end,
    approval rejection, approval timeout, unhandled exception).

    ``state_data`` keys:
      - ``workflow_id`` (str, required): the Temporal workflow_id (matches
        WorkflowRun.workflow_id, which has a unique index).
      - ``status`` (str, required): one of ``completed`` / ``failed`` /
        ``rejected`` / ``expired``.
      - ``summary`` (dict | None): optional error context (e.g.
        ``{"error": "<exception repr>"}``) — not persisted today but kept
        in the signature so a future column add is non-breaking.

    Failure mode: this activity logs and swallows DB errors. Re-raising would
    cause Temporal to retry the activity indefinitely on a permanent DB
    failure, which would mask the underlying workflow status. Operators see
    the orphaned ``started`` row + an ERROR log line and can reconcile
    manually.
    """
    from worker.db.session import SessionLocal
    from app.models.workflow import WorkflowRun

    workflow_id = state_data.get("workflow_id")
    status = state_data.get("status")
    if not workflow_id or not status:
        logger.error(
            "persist_workflow_terminal_state_activity called with missing fields: %s",
            state_data,
        )
        return

    db = SessionLocal()
    try:
        run = (
            db.query(WorkflowRun)
            .filter(WorkflowRun.workflow_id == workflow_id)
            .first()
        )
        if not run:
            logger.warning(
                "Terminal-state reconcile skipped — no WorkflowRun row for workflow_id=%s",
                workflow_id,
            )
            return
        run.status = status
        # Close the loop on project status: _persist_started_workflow flips the
        # project to "running" on start; revert it here so projects don't get
        # stuck "running" forever. Guard: don't downgrade while another run is
        # still active for the same project (last terminal run wins otherwise).
        from app.models.project import Project
        others_active = (
            db.query(WorkflowRun)
            .filter(
                WorkflowRun.project_id == run.project_id,
                WorkflowRun.workflow_id != workflow_id,
                WorkflowRun.status.in_(["started", "running", "awaiting_approval"]),
            )
            .first()
        )
        proj = db.query(Project).filter(Project.id == run.project_id).first()
        if proj is not None and proj.status not in ("archived", "deleted") and not others_active:
            proj.status = {"completed": "completed", "failed": "failed"}.get(status, "draft")
        db.commit()
        logger.info(
            "WorkflowRun %s reconciled to status=%s (summary=%s)",
            workflow_id,
            status,
            state_data.get("summary"),
        )
    except Exception as exc:  # noqa: BLE001
        # Swallow + log — see docstring "Failure mode" note above.
        logger.exception(
            "Failed to reconcile WorkflowRun %s to %s: %s",
            workflow_id,
            status,
            exc,
        )
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
    finally:
        db.close()
