"""LangGraph wiring for the BMAD migration pipeline.

13 agent nodes, each backed by a BMAD agent + BMAD task skill. The graph
makes BMAD's communication contract executable:

  - `winston_project_context` produces `project-context.md` — the persistent_facts
    file every downstream agent's customize.toml references.
  - Each subsequent node reads upstream artifacts from `planning_artifacts/`
    (BMAD's file-based handoff) and writes its own markdown artifact.
  - `approval_gate` is the conditional branch point — human input determines
    whether the implementation chain runs.

Conditional routing after `approval_gate`:
  - approval_decision == "approved" → continue to amelia_story → amelia_dev → ...
  - approval_decision == "rejected" → END (status="rejected")
  - approval_decision is None       → END (status="pending"; resume by re-invoking
                                      with approval_decision set)
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from agents.bmad.nodes import (
    amelia_code_review_node,
    amelia_dev_node,
    amelia_qa_node,
    amelia_story_node,
    approval_gate_node,
    john_prd_node,
    mary_analyze_node,
    paige_docs_node,
    sally_ux_node,
    winston_architecture_node,
    winston_project_context_node,
    winston_readiness_node,
    winston_stories_node,
)
from agents.bmad.schemas import BMADFinalOutput
from agents.bmad.state import BMADWorkflowState
from agents.runtime.artifact_store import planning_root_for_project


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_compiled_graph = None


def _approval_router(state: BMADWorkflowState) -> str:
    """Conditional edge from approval_gate."""
    decision = state.get("approval_decision")
    if decision == "approved":
        return "amelia_story"
    return "END"


def build_bmad_graph(force_rebuild: bool = False):
    """Compile (or return cached) BMAD migration graph."""
    global _compiled_graph
    if _compiled_graph is not None and not force_rebuild:
        return _compiled_graph

    graph = StateGraph(BMADWorkflowState)

    # Phase 0: shared-memory bootstrap.
    graph.add_node("winston_project_context", winston_project_context_node)
    # Phase 1: analysis.
    graph.add_node("mary_analyze", mary_analyze_node)
    # Phase 2: planning.
    graph.add_node("john_prd", john_prd_node)
    graph.add_node("sally_ux", sally_ux_node)
    # Phase 3: solutioning.
    graph.add_node("winston_architecture", winston_architecture_node)
    graph.add_node("winston_stories", winston_stories_node)
    graph.add_node("winston_readiness", winston_readiness_node)
    # Gate.
    graph.add_node("approval_gate", approval_gate_node)
    # Phase 4: implementation.
    graph.add_node("amelia_story", amelia_story_node)
    graph.add_node("amelia_dev", amelia_dev_node)
    graph.add_node("amelia_qa", amelia_qa_node)
    graph.add_node("amelia_code_review", amelia_code_review_node)
    # Phase 5: docs.
    graph.add_node("paige_docs", paige_docs_node)

    # Planning chain (linear).
    graph.add_edge(START, "winston_project_context")
    graph.add_edge("winston_project_context", "mary_analyze")
    graph.add_edge("mary_analyze", "john_prd")
    graph.add_edge("john_prd", "sally_ux")
    graph.add_edge("sally_ux", "winston_architecture")
    graph.add_edge("winston_architecture", "winston_stories")
    graph.add_edge("winston_stories", "winston_readiness")
    graph.add_edge("winston_readiness", "approval_gate")

    # Conditional branch.
    graph.add_conditional_edges(
        "approval_gate",
        _approval_router,
        {
            "amelia_story": "amelia_story",
            "END": END,
        },
    )

    # Implementation chain.
    graph.add_edge("amelia_story", "amelia_dev")
    graph.add_edge("amelia_dev", "amelia_qa")
    graph.add_edge("amelia_qa", "amelia_code_review")
    graph.add_edge("amelia_code_review", "paige_docs")
    graph.add_edge("paige_docs", END)

    _compiled_graph = graph.compile()
    return _compiled_graph


def _build_final_output(state: BMADWorkflowState) -> dict | None:
    outputs = state.get("outputs", {})
    return BMADFinalOutput(
        analyst=outputs.get("analyst"),
        pm=outputs.get("pm"),
        ux_designer=outputs.get("ux_designer"),
        architect=outputs.get("architect"),
        approval_gate=outputs.get("approval_gate"),
        dev=outputs.get("dev"),
        qa=outputs.get("qa"),
        code_review=outputs.get("code_review"),
        tech_writer=outputs.get("tech_writer"),
        status=state.get("status", "completed"),
    ).model_dump()


def run_bmad_graph(
    project_id: str,
    requirement_id: str,
    organization_id: str | None = None,
    requirement_text: str | None = None,
    approval_decision: str | None = None,
) -> dict:
    """Execute the BMAD planning + implementation graph end-to-end."""
    timestamp = _now()
    artifact_dir = planning_root_for_project(project_id)

    initial_state: BMADWorkflowState = {
        "project_id": project_id,
        "requirement_id": requirement_id,
        "organization_id": organization_id,
        "workflow_run_id": str(uuid4()),
        "current_agent": "winston_project_context",
        "status": "pending",
        "requirement_text": requirement_text,
        "artifact_dir": str(artifact_dir),
        "artifact_paths": {},
        "outputs": {},
        "errors": [],
        "approval_required": False,
        "approval_decision": approval_decision,
        "approval_notes": "",
        "created_at": timestamp,
        "updated_at": timestamp,
    }

    compiled = build_bmad_graph()
    final_state = dict(compiled.invoke(initial_state))

    errors = final_state.get("errors") or []
    decision = final_state.get("approval_decision")
    outputs = final_state.get("outputs", {})
    if errors:
        final_state["status"] = "failed"
    elif decision == "rejected":
        final_state["status"] = "rejected"
    elif decision == "approved" and "tech_writer" in outputs:
        final_state["status"] = "completed"
    elif decision is None and "approval_gate" in outputs:
        final_state["status"] = "pending"
    else:
        final_state["status"] = "running"

    final_state["final_output"] = _build_final_output(final_state)
    return final_state
