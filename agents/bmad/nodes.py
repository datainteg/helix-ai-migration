"""LangGraph nodes for the BMAD migration pipeline.

Each node maps to one BMAD agent + one BMAD task skill it invokes.
All heavy lifting lives in `agents.runtime.bmad_executor.execute_agent_skill`;
this file is intentionally thin — it just translates LangGraph state in/out.

Pipeline order (13 nodes, includes BMAD's project-context bootstrap):

  Phase 0: winston_project_context   Winston   → bmad-generate-project-context
  Phase 1: mary_analyze              Mary      → bmad-product-brief
  Phase 2: john_prd                  John      → bmad-prd        (replaces deprecated bmad-create-prd)
           sally_ux                  Sally     → bmad-create-ux-design
  Phase 3: winston_architecture      Winston   → bmad-create-architecture
           winston_stories           Winston   → bmad-create-epics-and-stories
           winston_readiness         Winston   → bmad-check-implementation-readiness
  ────── approval_gate (human, conditional) ──────
  Phase 4: amelia_story              Amelia    → bmad-create-story
           amelia_dev                Amelia    → bmad-dev-story
           amelia_qa                 Amelia    → bmad-qa-generate-e2e-tests
           amelia_code_review        Amelia    → bmad-code-review
  Phase 5: paige_docs                Paige     → bmad-document-project
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from agents.bmad.schemas import (
    AnalystOutput,
    ApprovalGateOutput,
    ArchitectOutput,
    CodeReviewOutput,
    DevOutput,
    PMOutput,
    QAOutput,
    TechWriterOutput,
    UXDesignerOutput,
)
from agents.bmad.state import BMADWorkflowState
from agents.runtime.bmad_executor import execute_agent_skill

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _apply_result(
    state: BMADWorkflowState,
    *,
    output_key: str,
    agent_code: str,
    result_parsed: Any,
    artifact_path: str | None,
    status: str = "running",
) -> BMADWorkflowState:
    outputs = dict(state.get("outputs", {}))
    outputs[output_key] = result_parsed.model_dump() if result_parsed else {}

    artifact_paths = dict(state.get("artifact_paths", {}))
    if artifact_path:
        artifact_paths.setdefault(agent_code, [])
        if artifact_path not in artifact_paths[agent_code]:
            artifact_paths[agent_code].append(artifact_path)

    return {
        **state,
        "outputs": outputs,
        "artifact_paths": artifact_paths,
        "current_agent": output_key,
        "status": status,
        "updated_at": _now(),
    }


def _apply_error(state: BMADWorkflowState, output_key: str, errors: list[str]) -> BMADWorkflowState:
    message = "; ".join(errors)
    logger.error("%s failed: %s", output_key, message)
    return {
        **state,
        "current_agent": output_key,
        "status": "failed",
        "errors": [*state.get("errors", []), f"{output_key}: {message}"],
        "updated_at": _now(),
    }


def _run(
    state: BMADWorkflowState,
    *,
    output_key: str,
    agent_code: str,
    skill_name: str,
    output_model: type,
    upstream_agents: list[str] | None = None,
    artifact_filename: str | None = None,
) -> BMADWorkflowState:
    overrides = state.get("prompt_overrides") or {}
    result = execute_agent_skill(
        agent_code=agent_code,
        skill_name=skill_name,
        project_id=state.get("project_id", "unknown"),
        requirement_text=state.get("requirement_text", "") or "",
        output_model=output_model,
        upstream_agents=upstream_agents or [],
        org_id=state.get("organization_id"),
        artifact_filename=artifact_filename,
        prompt_override=overrides.get(agent_code),
    )
    if not result.success or result.parsed is None:
        return _apply_error(state, output_key, result.errors or ["execution failed"])
    return _apply_result(
        state,
        output_key=output_key,
        agent_code=agent_code,
        result_parsed=result.parsed,
        artifact_path=str(result.artifact.path) if result.artifact else None,
    )


# ── Pipeline nodes (13 BMAD steps) ───────────────────────────────────


def winston_project_context_node(state: BMADWorkflowState) -> BMADWorkflowState:
    """Winston bootstraps the project-context.md file ALL agents load as persistent_facts.

    This is BMAD's shared-memory primitive: every agent's customize.toml declares
    `persistent_facts = ["file:{project-root}/**/project-context.md"]`. If we
    don't create the file, agents have no cross-session shared memory.
    """
    return _run(
        state,
        output_key="project_context",
        agent_code="bmad-agent-architect",
        skill_name="bmad-generate-project-context",
        output_model=ArchitectOutput,
        artifact_filename="project-context",
    )


def mary_analyze_node(state: BMADWorkflowState) -> BMADWorkflowState:
    """Mary (Business Analyst) → product brief."""
    return _run(
        state,
        output_key="analyst",
        agent_code="bmad-agent-analyst",
        skill_name="bmad-product-brief",
        output_model=AnalystOutput,
        upstream_agents=["bmad-agent-architect"],  # picks up project-context
        artifact_filename="product-brief",
    )


def john_prd_node(state: BMADWorkflowState) -> BMADWorkflowState:
    """John (PM) → PRD via bmad-prd (replaces deprecated bmad-create-prd)."""
    return _run(
        state,
        output_key="pm",
        agent_code="bmad-agent-pm",
        skill_name="bmad-prd",
        output_model=PMOutput,
        upstream_agents=["bmad-agent-architect", "bmad-agent-analyst"],
        artifact_filename="prd",
    )


def sally_ux_node(state: BMADWorkflowState) -> BMADWorkflowState:
    """Sally (UX) → UX flows."""
    return _run(
        state,
        output_key="ux_designer",
        agent_code="bmad-agent-ux-designer",
        skill_name="bmad-create-ux-design",
        output_model=UXDesignerOutput,
        upstream_agents=["bmad-agent-analyst", "bmad-agent-pm"],
        artifact_filename="ux-design",
    )


def winston_architecture_node(state: BMADWorkflowState) -> BMADWorkflowState:
    """Winston (Architect) → architecture decision record."""
    return _run(
        state,
        output_key="architect",
        agent_code="bmad-agent-architect",
        skill_name="bmad-create-architecture",
        output_model=ArchitectOutput,
        upstream_agents=["bmad-agent-analyst", "bmad-agent-pm", "bmad-agent-ux-designer"],
        artifact_filename="architecture",
    )


def winston_stories_node(state: BMADWorkflowState) -> BMADWorkflowState:
    """Winston (Architect) → epics + stories."""
    return _run(
        state,
        output_key="architect_stories",
        agent_code="bmad-agent-architect",
        skill_name="bmad-create-epics-and-stories",
        output_model=ArchitectOutput,
        upstream_agents=["bmad-agent-analyst", "bmad-agent-pm", "bmad-agent-architect"],
        artifact_filename="epics-and-stories",
    )


def winston_readiness_node(state: BMADWorkflowState) -> BMADWorkflowState:
    """Winston → check PRD/UX/Arch/Epics are complete BEFORE asking for human approval."""
    return _run(
        state,
        output_key="architect_readiness",
        agent_code="bmad-agent-architect",
        skill_name="bmad-check-implementation-readiness",
        output_model=ArchitectOutput,
        upstream_agents=[
            "bmad-agent-analyst",
            "bmad-agent-pm",
            "bmad-agent-ux-designer",
            "bmad-agent-architect",
        ],
        artifact_filename="implementation-readiness",
    )


def approval_gate_node(state: BMADWorkflowState) -> BMADWorkflowState:
    """Human approval gate — pure state transition, no LLM call."""
    decision = state.get("approval_decision")
    approval_required = decision is None
    if decision == "approved":
        reason = "Architecture and stories were approved by a human reviewer."
        next_step = "amelia_story"
        status = "running"
    elif decision == "rejected":
        reason = "Architecture or stories were rejected. Returning to planning."
        next_step = "revise_planning"
        status = "rejected"
    else:
        reason = "Human approval required before implementation agents continue."
        next_step = "await_human_approval"
        status = "pending"

    output = ApprovalGateOutput(
        approval_required=approval_required,
        approval_reason=reason,
        next_step=next_step,
    )

    outputs = dict(state.get("outputs", {}))
    outputs["approval_gate"] = output.model_dump()

    return {
        **state,
        "outputs": outputs,
        "current_agent": "approval_gate",
        "approval_required": approval_required,
        "status": status,
        "updated_at": _now(),
    }


def amelia_story_node(state: BMADWorkflowState) -> BMADWorkflowState:
    """Amelia → creates a dedicated story file with all implementation context.

    BMAD's pattern: build a self-contained story spec BEFORE attempting dev.
    """
    return _run(
        state,
        output_key="dev_story",
        agent_code="bmad-agent-dev",
        skill_name="bmad-create-story",
        output_model=DevOutput,
        upstream_agents=[
            "bmad-agent-analyst",
            "bmad-agent-pm",
            "bmad-agent-architect",
        ],
        artifact_filename="story",
    )


def amelia_dev_node(state: BMADWorkflowState) -> BMADWorkflowState:
    """Amelia (Dev) → implements migration story."""
    return _run(
        state,
        output_key="dev",
        agent_code="bmad-agent-dev",
        skill_name="bmad-dev-story",
        output_model=DevOutput,
        upstream_agents=[
            "bmad-agent-analyst",
            "bmad-agent-pm",
            "bmad-agent-architect",
            "bmad-agent-dev",  # pick up the story file from amelia_story
        ],
        artifact_filename="dev-implementation",
    )


def amelia_qa_node(state: BMADWorkflowState) -> BMADWorkflowState:
    """Amelia → generates E2E tests."""
    return _run(
        state,
        output_key="qa",
        agent_code="bmad-agent-dev",
        skill_name="bmad-qa-generate-e2e-tests",
        output_model=QAOutput,
        upstream_agents=["bmad-agent-dev"],
        artifact_filename="qa-tests",
    )


def amelia_code_review_node(state: BMADWorkflowState) -> BMADWorkflowState:
    """Amelia → runs adversarial code review on the generated migration code."""
    return _run(
        state,
        output_key="code_review",
        agent_code="bmad-agent-dev",
        skill_name="bmad-code-review",
        output_model=CodeReviewOutput,
        upstream_agents=["bmad-agent-dev"],
        artifact_filename="code-review",
    )


def paige_docs_node(state: BMADWorkflowState) -> BMADWorkflowState:
    """Paige (Tech Writer) → migration documentation."""
    return _run(
        state,
        output_key="tech_writer",
        agent_code="bmad-agent-tech-writer",
        skill_name="bmad-document-project",
        output_model=TechWriterOutput,
        upstream_agents=[
            "bmad-agent-analyst",
            "bmad-agent-pm",
            "bmad-agent-architect",
            "bmad-agent-dev",
        ],
        artifact_filename="migration-docs",
    )
