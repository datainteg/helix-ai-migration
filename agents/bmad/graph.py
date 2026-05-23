from datetime import datetime, timezone
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from agents.bmad.nodes import (
    approval_gate_node,
    architect_node,
    business_analyst_node,
    validation_planner_node,
)
from agents.bmad.schemas import BMADFinalOutput
from agents.bmad.state import BMADWorkflowState


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Cached compiled graph — built once, reused across all invocations
_compiled_graph = None


def build_bmad_graph():
    """Build the BMAD LangGraph StateGraph. Cached after first compilation."""
    global _compiled_graph
    if _compiled_graph is not None:
        return _compiled_graph

    graph = StateGraph(BMADWorkflowState)
    graph.add_node("business_analyst", business_analyst_node)
    graph.add_node("architect", architect_node)
    graph.add_node("validation_planner", validation_planner_node)
    graph.add_node("approval_gate", approval_gate_node)

    graph.add_edge(START, "business_analyst")
    graph.add_edge("business_analyst", "architect")
    graph.add_edge("architect", "validation_planner")
    graph.add_edge("validation_planner", "approval_gate")
    graph.add_edge("approval_gate", END)

    return graph.compile()


def _build_final_output(state: BMADWorkflowState) -> dict | None:
    outputs = state.get("outputs", {})
    required_outputs = {"business_analyst", "architect", "validation_planner", "approval_gate"}
    if not required_outputs.issubset(outputs):
        return None

    final_output = BMADFinalOutput(
        business_analysis=outputs["business_analyst"],
        architecture=outputs["architect"],
        validation_plan=outputs["validation_planner"],
        approval_gate=outputs["approval_gate"],
        status=state.get("status", "completed"),
    )
    return final_output.model_dump()


def run_bmad_graph(
    project_id: str,
    requirement_id: str,
    organization_id: str | None = None,
    requirement_text: str | None = None,
    approval_decision: str | None = None,
) -> dict:
    timestamp = _now()
    initial_state: BMADWorkflowState = {
        "project_id": project_id,
        "requirement_id": requirement_id,
        "organization_id": organization_id,
        "workflow_run_id": str(uuid4()),
        "current_agent": "business_analyst",
        "status": "pending",
        "requirement_text": requirement_text,
        "outputs": {},
        "errors": [],
        "approval_required": False,
        "approval_decision": approval_decision,
        "created_at": timestamp,
        "updated_at": timestamp,
    }

    compiled_graph = build_bmad_graph()
    final_state = dict(compiled_graph.invoke(initial_state))
    final_output = _build_final_output(final_state)
    if final_output is not None:
        final_state["final_output"] = final_output
    return final_state
