from typing import Any, Literal, TypedDict


WorkflowStatus = Literal["pending", "running", "completed", "failed"]
ApprovalDecision = Literal["approved", "rejected"]


class BMADWorkflowState(TypedDict, total=False):
    project_id: str
    requirement_id: str
    organization_id: str | None
    workflow_run_id: str
    current_agent: str
    status: WorkflowStatus
    requirement_text: str | None
    outputs: dict[str, dict[str, Any]]
    errors: list[str]
    approval_required: bool
    approval_decision: ApprovalDecision | None
    created_at: str
    updated_at: str
