import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from agents.bmad.schemas import (
    ApprovalGateOutput,
    ArchitectOutput,
    BusinessAnalystOutput,
    RiskItem,
    ValidationPlanOutput,
)
from agents.bmad.official_agents import get_official_agent_metadata
from agents.bmad.state import BMADWorkflowState

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


def _state_with_error(state: BMADWorkflowState, agent_name: str, error: ValidationError) -> BMADWorkflowState:
    message = f"{agent_name} output validation failed: {error.errors()}"
    logger.error(message)
    return {
        **state,
        "current_agent": agent_name,
        "status": "failed",
        "errors": [*state.get("errors", []), message],
        "updated_at": _now(),
    }


def business_analyst_node(state: BMADWorkflowState) -> BMADWorkflowState:
    agent = get_official_agent_metadata("business_analyst")
    try:
        output = BusinessAnalystOutput(
            summary=f"{agent['name']} ({agent['title']}) completed initial migration requirement analysis.",
            business_goals=[
                "Clarify migration objective and business success criteria.",
                "Identify source-to-target planning assumptions before engineering work starts.",
            ],
            assumptions=[
                "The current requirement text is the authoritative planning input.",
                "Source and target metadata will be refined before implementation planning.",
            ],
            open_questions=[
                "What is the required cutover window?",
                "Which source systems are in scope for the MVP validation plan?",
            ],
            risks=[
                RiskItem(
                    title="Incomplete migration scope",
                    severity="medium",
                    impact="Planning outputs may miss critical systems or validation needs.",
                    mitigation="Review the requirement with business owners before architecture approval.",
                )
            ],
        )
    except ValidationError as error:
        return _state_with_error(state, "business_analyst", error)
    return _state_with_output(state, "business_analyst", output.model_dump())


def architect_node(state: BMADWorkflowState) -> BMADWorkflowState:
    agent = get_official_agent_metadata("architect")
    try:
        output = ArchitectOutput(
            architecture_summary=f"{agent['name']} ({agent['title']}) prepared the draft source-to-target migration architecture.",
            source_systems=["source system metadata pending"],
            target_systems=["target platform metadata pending"],
            integration_points=[
                "Metadata capture API",
                "Agent planning workflow",
                "Validation and reconciliation reporting",
            ],
            dependencies=[
                "Approved business requirement",
                "Confirmed source and target metadata",
                "Configured LLM provider or mock-mode fallback",
            ],
            risks=[
                RiskItem(
                    title="Architecture approval gap",
                    severity="high",
                    impact="Execution-oriented planning could proceed without human confirmation.",
                    mitigation="Require approval gate review before later BMAD migration agents run.",
                )
            ],
        )
    except ValidationError as error:
        return _state_with_error(state, "architect", error)
    return _state_with_output(state, "architect", output.model_dump())


def validation_planner_node(state: BMADWorkflowState) -> BMADWorkflowState:
    try:
        output = ValidationPlanOutput(
            validation_strategy="Create metadata-driven validation and reconciliation checks before migration execution.",
            checks=[
                "Schema compatibility check",
                "Row count comparison",
                "Null and duplicate summary",
                "Business-rule acceptance check",
            ],
            reconciliation_approach="Compare source and target metadata summaries first; defer row-level reconciliation to later phases.",
            acceptance_criteria=[
                "Business goals are reviewed.",
                "Architecture plan is approved.",
                "Validation and reconciliation checks are explicitly listed.",
            ],
            risks=[
                RiskItem(
                    title="Validation rules not finalized",
                    severity="medium",
                    impact="Generated plan may not prove migration correctness.",
                    mitigation="Capture validation expectations during requirement intake and approval review.",
                )
            ],
        )
    except ValidationError as error:
        return _state_with_error(state, "validation_planner", error)
    return _state_with_output(state, "validation_planner", output.model_dump())


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

    try:
        output = ApprovalGateOutput(
            approval_required=approval_required,
            approval_reason=reason,
            next_step=next_step,
        )
    except ValidationError as error:
        return _state_with_error(state, "approval_gate", error)

    next_state = _state_with_output(state, "approval_gate", output.model_dump())
    return {
        **next_state,
        "approval_required": approval_required,
        "status": "completed",
        "updated_at": _now(),
    }
