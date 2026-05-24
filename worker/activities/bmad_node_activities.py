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

import json
import logging
from typing import Any

from temporalio import activity

logger = logging.getLogger(__name__)


def _execute(
    agent_code: str,
    skill_name: str,
    output_model_name: str,
    input_data: dict[str, Any],
    upstream_agents: list[str] | None = None,
    artifact_filename: str | None = None,
) -> dict[str, Any]:
    """Resolve output model by name and run an agent+skill (synchronous)."""
    from agents.bmad import schemas as bmad_schemas
    from agents.runtime.bmad_executor import execute_agent_skill

    output_model = getattr(bmad_schemas, output_model_name)
    result = execute_agent_skill(
        agent_code=agent_code,
        skill_name=skill_name,
        project_id=input_data.get("project_id", "unknown"),
        requirement_text=input_data.get("requirement_text", "") or "",
        output_model=output_model,
        upstream_agents=upstream_agents or [],
        org_id=input_data.get("organization_id"),
        artifact_filename=artifact_filename,
        correlation_id=input_data.get("correlation_id"),
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

    Synchronous activity — opens a sync SQLAlchemy session and always closes it.
    """
    from app.db.session import SessionLocal
    from app.services.workflow_service import save_workflow_step

    db = SessionLocal()
    try:
        parsed = step_data.get("parsed") or {}
        save_workflow_step(
            db,
            workflow_run_id=step_data["workflow_run_id"],
            agent_name=step_data["agent_name"],
            step_order=step_data["step_order"],
            status=step_data.get("status", "completed"),
            raw_output=json.dumps({**parsed, "artifact_path": step_data.get("artifact_path")}),
            parsed_output_json=parsed,
            provider_name=step_data.get("mode"),
            model_name=step_data.get("model_name"),
            error_message="; ".join(step_data.get("errors", [])) or None,
        )
    finally:
        db.close()
