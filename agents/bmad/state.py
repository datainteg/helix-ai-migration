"""State schema for the BMAD LangGraph workflow.

State is passed between every node. Each node:
  - reads `requirement_text`, prior `outputs`, prior `artifact_paths`
  - performs its LLM call via BMAD persona + skill
  - appends to `outputs` (compact summary for UI/DB) and `artifact_paths`
    (absolute paths to the markdown artifacts it produced)

`artifact_dir` is the per-project planning-artifacts root, resolved via
`agents.runtime.artifact_store.planning_root_for_project()` at graph entry.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict


WorkflowStatus = Literal["pending", "running", "completed", "failed", "rejected"]
ApprovalDecision = Literal["approved", "rejected"]


class BMADWorkflowState(TypedDict, total=False):
    # Identifiers
    project_id: str
    requirement_id: str
    organization_id: str | None
    workflow_run_id: str

    # Execution state
    current_agent: str
    status: WorkflowStatus
    errors: list[str]

    # Inputs
    requirement_text: str | None

    # BMAD artifact context
    artifact_dir: str  # absolute path to {planning_artifacts}/{project_id}/
    artifact_paths: dict[str, list[str]]  # agent_code -> [absolute artifact paths]

    # Agent outputs (compact summaries for UI + DB persistence)
    outputs: dict[str, dict[str, Any]]

    # Approval gate
    approval_required: bool
    approval_decision: ApprovalDecision | None
    approval_notes: str

    # Timestamps
    created_at: str
    updated_at: str
