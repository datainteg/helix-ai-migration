"""HelixBMAD — Class facade for the BMAD workflow.

Single import point for both backend and worker:

    from agents import HelixBMAD

    # Local synchronous run (LangGraph in-process; useful for dev + tests).
    result = HelixBMAD(
        project_id="proj-123",
        requirement_id="req-456",
        organization_id="org-789",
        requirement_text="Migrate Salesforce → Snowflake",
    ).run()

    # Or kick off via Temporal (durable, retried, signal-driven approval).
    handle = await workflow.start_temporal()
    # ... wait on Temporal ...
    workflow.resume(approval="approved", notes="LGTM")

    # Status + artifact inspection.
    workflow.list_artifacts()
    workflow.get_status()

The class wraps the lower-level functions in `agents.bmad.graph` +
`agents.runtime.bmad_executor` + `agents.runtime.artifact_store`. Use it
instead of touching those modules directly from outside the package.
"""

from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class HelixBMADResult:
    """Outcome of a HelixBMAD run."""

    workflow_id: str
    run_id: str
    status: str            # pending | running | completed | rejected | failed
    mode: str              # local | temporal
    outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    artifact_paths: dict[str, list[str]] = field(default_factory=dict)
    artifact_dir: str = ""
    errors: list[str] = field(default_factory=list)
    final_output: dict[str, Any] | None = None
    correlation_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class HelixBMAD:
    """Class-based facade around the BMAD agent workflow.

    Parameters
    ----------
    project_id : str
        Helix project identifier — used as artifact-store key and Temporal workflow ID seed.
    requirement_id : str
        Migration requirement identifier (foreign key into backend's MigrationRequirement).
    requirement_text : str
        The actual requirement text the BMAD agents will plan against.
    organization_id : str | None
        Helix org ID — passed through to `call_llm` so it can scope the LLMProvider
        + LLMAgentMapping queries.
    approval_decision : str | None
        Set to "approved" / "rejected" when resuming after a human approval gate.
    workflow_run_id : str | None
        Pre-allocated run ID. If omitted, a new UUID is generated on first use.
    temporal_address : str | None
        Override the Temporal target address (defaults to `TEMPORAL_ADDRESS` env).
    task_queue : str | None
        Override the Temporal task queue (defaults to `TEMPORAL_TASK_QUEUE` env).
    """

    DEFAULT_TASK_QUEUE = "helix-bmad-task-queue"
    DEFAULT_TEMPORAL_ADDRESS = "localhost:7233"

    def __init__(
        self,
        *,
        project_id: str,
        requirement_id: str,
        requirement_text: str,
        organization_id: str | None = None,
        approval_decision: str | None = None,
        approval_notes: str = "",
        workflow_run_id: str | None = None,
        temporal_address: str | None = None,
        task_queue: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        if not project_id:
            raise ValueError("project_id is required")
        if not requirement_id:
            raise ValueError("requirement_id is required")

        self.project_id = project_id
        self.requirement_id = requirement_id
        self.requirement_text = requirement_text or ""
        self.organization_id = organization_id
        self.approval_decision = approval_decision
        self.approval_notes = approval_notes
        self.workflow_run_id = workflow_run_id or str(uuid4())
        # Propagate request-id end-to-end. Defaults to the workflow_run_id so
        # logs always carry a stable trace key even for non-HTTP-triggered runs.
        self.correlation_id = correlation_id or self.workflow_run_id
        self.temporal_address = temporal_address or os.getenv(
            "TEMPORAL_ADDRESS", self.DEFAULT_TEMPORAL_ADDRESS
        )
        self.task_queue = task_queue or os.getenv("TEMPORAL_TASK_QUEUE", self.DEFAULT_TASK_QUEUE)

    # ── Identifiers ─────────────────────────────────────────────────

    @property
    def workflow_id(self) -> str:
        """Stable workflow ID used as Temporal workflow handle."""
        return f"bmad-{self.project_id}-{self.requirement_id}"

    @property
    def artifact_dir(self) -> Path:
        from agents.runtime.artifact_store import planning_root_for_project

        return planning_root_for_project(self.project_id)

    # ── Synchronous local run (LangGraph in-process) ────────────────

    def run(self) -> HelixBMADResult:
        """Execute the BMAD LangGraph synchronously and return the final result.

        Suitable for dev/test, or as the local fallback when Temporal is unavailable.
        Production code should prefer `start_temporal()`.
        """
        from agents.bmad.graph import run_bmad_graph

        state = run_bmad_graph(
            project_id=self.project_id,
            requirement_id=self.requirement_id,
            organization_id=self.organization_id,
            requirement_text=self.requirement_text,
            approval_decision=self.approval_decision,
        )
        return HelixBMADResult(
            workflow_id=self.workflow_id,
            run_id=state.get("workflow_run_id", self.workflow_run_id),
            status=state.get("status", "unknown"),
            mode="local",
            outputs=state.get("outputs", {}),
            artifact_paths=state.get("artifact_paths", {}),
            artifact_dir=state.get("artifact_dir", str(self.artifact_dir)),
            errors=state.get("errors", []),
            final_output=state.get("final_output"),
            correlation_id=self.correlation_id,
        )

    # ── Temporal — durable, signal-driven approval ──────────────────

    async def start_temporal(self) -> HelixBMADResult:
        """Submit `BMADPerNodeWorkflow` to Temporal and return immediately.

        Returns a `HelixBMADResult` with `status="started"`. Poll
        `get_temporal_status()` or send `resume(...)` to drive the human gate.
        """
        from temporalio.client import Client

        from worker.workflows.bmad_per_node_workflow import BMADPerNodeWorkflow

        client = await Client.connect(self.temporal_address)
        handle = await client.start_workflow(
            BMADPerNodeWorkflow.run,
            self._input_payload(),
            id=self.workflow_id,
            task_queue=self.task_queue,
        )
        return HelixBMADResult(
            workflow_id=self.workflow_id,
            run_id=handle.result_run_id,
            status="started",
            mode="temporal",
            artifact_dir=str(self.artifact_dir),
            correlation_id=self.correlation_id,
        )

    async def resume(self, *, approval: str, notes: str = "") -> None:
        """Send the human approval signal (approve|reject) to a waiting workflow."""
        from temporalio.client import Client

        if approval not in {"approved", "rejected"}:
            raise ValueError("approval must be 'approved' or 'rejected'")
        client = await Client.connect(self.temporal_address)
        handle = client.get_workflow_handle(self.workflow_id)
        signal_name = "approve" if approval == "approved" else "reject"
        await handle.signal(signal_name, notes)
        self.approval_decision = approval
        self.approval_notes = notes

    async def get_temporal_status(self) -> dict[str, Any]:
        """Query Temporal for the current workflow execution state."""
        from temporalio.client import Client

        client = await Client.connect(self.temporal_address)
        handle = client.get_workflow_handle(self.workflow_id)
        desc = await handle.describe()
        return {
            "workflow_id": self.workflow_id,
            "run_id": desc.run_id,
            "status": desc.status.name if desc.status else "unknown",
            "task_queue": desc.task_queue,
            "start_time": str(desc.start_time) if desc.start_time else None,
        }

    # ── Ad-hoc artifact review (Developer Workspace) ────────────────

    def review_artifact(
        self,
        *,
        source_code: str,
        filename: str,
        intent: str = "review",
    ) -> "HelixBMADResult":
        """Run an ad-hoc BMAD code review on a single source file.

        `intent="review"` → Amelia invokes bmad-code-review (adversarial review with
            Blind Hunter + Edge Case Hunter + Acceptance Auditor layers).
        `intent="analyze"` → Amelia invokes bmad-investigate (forensic walkthrough
            of unfamiliar code).

        Used by `/artifacts/{id}/analyze` and `/artifacts/{id}/review` endpoints.
        Bypasses the multi-agent migration pipeline — this is a single agent + single
        skill, scoped to one source file.
        """
        from agents.bmad.schemas import CodeReviewOutput, DevOutput
        from agents.runtime.bmad_executor import execute_agent_skill

        if intent == "review":
            skill_name = "bmad-code-review"
            output_model = CodeReviewOutput
        elif intent == "analyze":
            skill_name = "bmad-investigate"
            output_model = DevOutput
        else:
            raise ValueError(f"intent must be 'review' or 'analyze', got {intent!r}")

        result = execute_agent_skill(
            agent_code="bmad-agent-dev",
            skill_name=skill_name,
            project_id=self.project_id,
            requirement_text=(
                f"File: {filename}\n\n"
                f"```\n{source_code[:8000]}\n```\n\n"
                f"Run {skill_name} on this file. Output a single markdown document with YAML frontmatter."
            ),
            output_model=output_model,
            upstream_agents=[],
            org_id=self.organization_id,
            artifact_filename=f"{intent}-{filename}",
            correlation_id=self.correlation_id,
        )

        # ── Local AST/regex fallback for code review ─────────────────
        # When the LLM path fails AND we're doing a review, run the
        # deterministic static analyser so the operator gets *something*
        # actionable instead of an empty findings list. The status
        # `completed_fallback` lets the API distinguish this from a
        # successful LLM review.
        if not result.success and intent == "review":
            from agents.runtime.static_analysis import analyze_python_source

            try:
                fallback_dict = analyze_python_source(source_code, filename)
            except Exception as exc:  # pragma: no cover — defensive only
                logger.exception("static_analysis fallback crashed: %s", exc)
                fallback_dict = {
                    "summary": f"Static analysis fallback crashed: {exc}",
                    "findings": [],
                    "blocking_issues": [],
                    "sign_off": "needs_revision",
                    "artifacts": [],
                    "risk_level": "LOW",
                    "structured_findings": [],
                }
            return HelixBMADResult(
                workflow_id=f"adhoc-{intent}-{self.project_id}-{filename}",
                run_id=f"adhoc-{intent}-{self.project_id}",
                status="completed_fallback",
                mode="local",
                outputs={intent: fallback_dict},
                artifact_paths={"bmad-agent-dev": []},
                artifact_dir=str(self.artifact_dir),
                errors=result.errors,
            )

        return HelixBMADResult(
            workflow_id=f"adhoc-{intent}-{self.project_id}-{filename}",
            run_id=f"adhoc-{intent}-{self.project_id}",
            status="completed" if result.success else "failed",
            mode="local",
            outputs={intent: result.parsed.model_dump() if result.parsed else {}},
            artifact_paths={"bmad-agent-dev": [str(result.artifact.path)] if result.artifact else []},
            artifact_dir=str(self.artifact_dir),
            errors=result.errors,
        )

    # ── Artifact + status inspection ────────────────────────────────

    def list_artifacts(self) -> list[dict[str, Any]]:
        """Return summary dicts for every artifact this project has produced."""
        from agents.runtime.artifact_store import list_artifacts

        return [art.to_summary() for art in list_artifacts(self.project_id)]

    def get_artifact(self, agent_code: str, filename: str = "") -> dict[str, Any] | None:
        """Return the latest artifact for (agent_code, filename slug)."""
        from agents.runtime.artifact_store import read_latest

        if not filename:
            from agents.runtime.artifact_store import list_artifacts

            arts = list_artifacts(self.project_id, agent_code=agent_code)
            return arts[-1].to_summary() if arts else None
        art = read_latest(self.project_id, agent_code, filename)
        return art.to_summary() if art else None

    # ── Internals ───────────────────────────────────────────────────

    def _input_payload(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "requirement_id": self.requirement_id,
            "organization_id": self.organization_id,
            "requirement_text": self.requirement_text,
            "approval_decision": self.approval_decision,
            "workflow_run_id": self.workflow_run_id,
            "correlation_id": self.correlation_id,
        }

    def __repr__(self) -> str:
        return (
            f"HelixBMAD(project_id={self.project_id!r}, requirement_id={self.requirement_id!r}, "
            f"workflow_id={self.workflow_id!r}, status_pending_approval={self.approval_decision is None})"
        )
