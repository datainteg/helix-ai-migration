import json
import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from agents.bmad.schemas import (
    ApprovalGateOutput,
    ArchitectOutput,
    BusinessAnalystOutput,
    ValidationPlanOutput,
)
from agents.bmad.state import BMADWorkflowState
from agents.runtime.llm_router import build_mock_agent_prompt, route_llm_call
from agents.runtime.structured_output import build_mock_agent_response, parse_router_result

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_with_output(state: BMADWorkflowState, agent_name: str, output: dict[str, Any]) -> BMADWorkflowState:
    outputs = dict(state.get("outputs", {}))
    outputs[agent_name] = output
    return {
        **state,
        "outputs": outputs,
        "current_agent": agent_name,
        "status": "running",
        "updated_at": _now(),
    }


def _state_with_error(state: BMADWorkflowState, agent_name: str, message: str) -> BMADWorkflowState:
    logger.error("%s output failed: %s", agent_name, message)
    return {
        **state,
        "current_agent": agent_name,
        "status": "failed",
        "errors": [*state.get("errors", []), f"{agent_name}: {message}"],
        "updated_at": _now(),
    }


def _run_agent_node(
    state: BMADWorkflowState,
    output_key: str,
    output_model: type[BaseModel],
    *,
    metadata_key: str | None = None,
) -> BMADWorkflowState:
    """Route an agent node through LLM router with mock fallback.

    output_key: the key written to state["outputs"] (stable contract with callers)
    metadata_key: the key used for llm_router/agent metadata lookup (may differ)
    Reads requirement_text from state so nodes use actual planning input.
    """
    agent_key = metadata_key or output_key
    requirement_text = state.get("requirement_text", "")
    prompt = build_mock_agent_prompt(agent_key, requirement_text)

    mock_result = build_mock_agent_response(agent_key, output_model, requirement_text=requirement_text)
    mock_json = json.dumps(mock_result.parsed.model_dump() if mock_result.success and mock_result.parsed else {})

    router_result = route_llm_call(
        agent_name=agent_key,
        prompt=prompt,
        mock_response=mock_json,
    )

    parsed = parse_router_result(router_result, output_model)
    if not parsed.success or parsed.parsed is None:
        error_msg = "; ".join(parsed.errors)
        return _state_with_error(state, output_key, error_msg)

    return _state_with_output(state, output_key, parsed.parsed.model_dump())


def business_analyst_node(state: BMADWorkflowState) -> BMADWorkflowState:
    return _run_agent_node(state, "business_analyst", BusinessAnalystOutput)


def architect_node(state: BMADWorkflowState) -> BMADWorkflowState:
    return _run_agent_node(state, "architect", ArchitectOutput)


def validation_planner_node(state: BMADWorkflowState) -> BMADWorkflowState:
    return _run_agent_node(state, "validation_planner", ValidationPlanOutput, metadata_key="qa_validation")


def approval_gate_node(state: BMADWorkflowState) -> BMADWorkflowState:
    decision = state.get("approval_decision")
    approval_required = decision is None
    if decision == "approved":
        reason = "Architecture and validation planning were approved."
        next_step = "continue_to_execution_planning"
    elif decision == "rejected":
        reason = "Architecture and validation planning were rejected."
        next_step = "revise_business_analysis_or_architecture"
    else:
        reason = "Human approval is required before execution-oriented BMAD agents continue."
        next_step = "await_human_approval"

    output = ApprovalGateOutput(
        approval_required=approval_required,
        approval_reason=reason,
        next_step=next_step,
    )

    next_state = _state_with_output(state, "approval_gate", output.model_dump())
    return {
        **next_state,
        "approval_required": approval_required,
        "status": "completed",
        "updated_at": _now(),
    }
