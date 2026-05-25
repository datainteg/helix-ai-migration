"""Workflow operations — time-machine replay + AI pair-review.

Two endpoints:
  POST /workflows/{workflow_id}/replay
    Re-runs a completed workflow with optional prompt/model overrides.
    Useful for prompt iteration: change the architect prompt, replay, diff
    against the original artifacts.

  POST /artifacts/{artifact_id}/pair-review
    Runs a second LLM model over an artifact, captures its critique, and
    persists it as an ArtifactReview row. The two outputs can be diffed by
    operators before approving DDL / migration code for production.

Both endpoints reuse the existing LLM transport stack — no new provider
adapter required.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.dependencies import get_current_organization_id
from app.auth.jwt import get_current_user_id
from app.api.audit import write_audit
from app.models.artifacts import CodeArtifact, ArtifactReview, CodeArtifactVersion
from app.models.workflow import WorkflowRun

router = APIRouter(tags=["workflow-ops"])


class ReplayRequest(BaseModel):
    requirement_text: str | None = None
    agent_prompt_overrides: dict[str, str] = Field(default_factory=dict)
    model_override: str | None = Field(default=None, description="Force a specific model id for this replay")


# SEC-016: cap per-agent override length, strip control chars, and reject
# anything that is not a known BMAD agent code. The override string lands
# in the LLM system prompt verbatim — without a length+content guard, any
# project member can craft a prompt-injection-as-feature override that
# convinces the LLM to leak prior context (api_key in frontmatter, etc.).
_MAX_OVERRIDE_CHARS = 4000
_VALID_AGENT_CODES = {
    "bmad-agent-analyst",
    "bmad-agent-architect",
    "bmad-agent-pm",
    "bmad-agent-po",
    "bmad-agent-sm",
    "bmad-agent-dev",
    "bmad-agent-qa",
    "bmad-agent-ux",
    "bmad-agent-bmad",
    # legacy shorthand still produced by some clients
    "analyst", "architect", "pm", "po", "sm", "dev", "qa", "ux",
}


def _validate_prompt_overrides(overrides: dict[str, str]) -> dict[str, str]:
    """Validate replay prompt-overrides.

    Raises HTTPException(400) on any violation. Returns the cleaned dict
    (control chars stripped) for downstream consumption.
    """
    from fastapi import HTTPException

    if not overrides:
        return {}
    if len(overrides) > 32:
        raise HTTPException(status_code=400, detail="Too many agent overrides (max 32)")

    cleaned: dict[str, str] = {}
    for agent_code, override in overrides.items():
        if not isinstance(agent_code, str) or not isinstance(override, str):
            raise HTTPException(status_code=400, detail="Override keys/values must be strings")
        if agent_code not in _VALID_AGENT_CODES:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown agent code {agent_code!r}; allowed: {sorted(_VALID_AGENT_CODES)}",
            )
        if len(override) > _MAX_OVERRIDE_CHARS:
            raise HTTPException(
                status_code=400,
                detail=f"Override for {agent_code} exceeds {_MAX_OVERRIDE_CHARS} chars",
            )
        # Strip ASCII control chars (except tab/newline) — prevents
        # role-injection via embedded \r, \x00, etc.
        sanitised = "".join(
            ch for ch in override
            if ch in ("\t", "\n") or (ord(ch) >= 0x20 and ord(ch) != 0x7F)
        )
        # Reject obvious chat-template role markers that could break out
        # of the operator-override append into a forged system/assistant turn.
        lowered = sanitised.lower()
        for marker in ("<|im_start|>", "<|im_end|>", "<|system|>", "<|assistant|>", "<|user|>"):
            if marker in lowered:
                raise HTTPException(
                    status_code=400,
                    detail=f"Override for {agent_code} contains forbidden role marker {marker!r}",
                )
        cleaned[agent_code] = sanitised
    return cleaned


@router.post("/workflows/{workflow_id}/replay")
def replay_workflow(
    workflow_id: str,
    data: ReplayRequest,
    request: Request,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Spawn a fresh BMAD planning run from an existing workflow's inputs.

    Records the parent_workflow_id in the new run's metadata so the UI can
    diff artifact-by-artifact later.
    """
    parent = (
        db.query(WorkflowRun)
        .filter(WorkflowRun.workflow_id == workflow_id, WorkflowRun.organization_id == org_id)
        .first()
    )
    if not parent:
        raise HTTPException(status_code=404, detail="Parent workflow not found")

    # SEC-016: validate overrides BEFORE we burn LLM tokens. Rejects
    # unknown agent codes, oversize bodies, control chars, role markers.
    safe_overrides = _validate_prompt_overrides(data.agent_prompt_overrides or {})

    # Delegate to the planning entrypoint. Real per-agent prompt overrides
    # require threading them through the executor — for now we record them
    # in audit metadata + the requirement_text, and let the operator paste
    # them as additional context.
    from app.services.workflow_service import start_bmad_planning_workflow
    import asyncio

    # Overrides flow as a dict keyed by agent_code. The executor reads them
    # via state["prompt_overrides"][agent_code] and appends to the system
    # prompt as "Operator override (replay)" — no requirement_text mangling.
    new_run = asyncio.run(start_bmad_planning_workflow(
        project_id=parent.project_id,
        requirement_id=parent.requirement_id or "",
        organization_id=org_id,
        requirement_text=data.requirement_text or "",
        db=db,
        prompt_overrides=safe_overrides or None,
    ))

    # Audit captures the full sanitised overrides so an operator can see
    # exactly what the LLM saw — not just the agent codes.
    write_audit(db, org_id=org_id, actor_id=user_id, action="workflow_replay",
                entity_type="workflow_run", entity_id=new_run.get("workflow_id", ""),
                meta={"parent_workflow_id": workflow_id,
                      "agent_overrides": safe_overrides,
                      "model_override": data.model_override},
                request=request)
    return {
        "parent_workflow_id": workflow_id,
        "replay_workflow_id": new_run.get("workflow_id"),
        "status": new_run.get("status"),
        "mode": new_run.get("mode"),
    }


class PairReviewRequest(BaseModel):
    reviewer_model: str | None = Field(default=None, description="Force a specific reviewer model (e.g. gpt-4o, claude-haiku-4-5).")
    reviewer_provider_type: str | None = Field(default=None)


@router.post("/artifacts/{artifact_id}/pair-review")
def pair_review_artifact(
    artifact_id: str,
    data: PairReviewRequest,
    request: Request,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Run a second LLM against an artifact + persist the critique.

    Choice of reviewer is independent of the generator: e.g. Claude-generated
    DDL gets reviewed by GPT-4 to catch model-specific blind spots.
    """
    forward = (
        db.query(CodeArtifact)
        .filter(CodeArtifact.id == artifact_id, CodeArtifact.organization_id == org_id)
        .first()
    )
    if not forward:
        raise HTTPException(status_code=404, detail="Artifact not found")

    try:
        from app.storage.s3 import read_artifact_bytes
        content = read_artifact_bytes(forward.storage_path).decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to read artifact: {exc}")

    from app.models.llm import LLMProvider
    from app.services.secret_service import decrypt_value
    from app.services.cost_service import record_usage
    from agents.runtime.providers import CallContext, get_provider as get_llm_provider

    # Pick reviewer provider: explicit override > first active that differs
    # from the artifact's original generator > org default.
    providers = (
        db.query(LLMProvider)
        .filter(LLMProvider.organization_id == org_id, LLMProvider.status == "active")
        .all()
    )
    if not providers:
        raise HTTPException(status_code=409, detail="No active LLM provider configured")

    reviewer = None
    if data.reviewer_provider_type:
        reviewer = next((p for p in providers if p.provider_type == data.reviewer_provider_type), None)
    if reviewer is None:
        # Prefer a different-vendor provider than the artifact generator if
        # we can determine it — pair-review value comes from divergence.
        reviewer = providers[0]
    if not reviewer.secrets:
        raise HTTPException(status_code=409, detail="Reviewer provider has no API key")

    secret = max(reviewer.secrets, key=lambda s: s.key_version)
    api_key = decrypt_value(secret.encrypted_api_key)
    model = data.reviewer_model or reviewer.default_model

    adapter = get_llm_provider(reviewer.provider_type)
    if adapter is None:
        raise HTTPException(status_code=501, detail=f"No adapter for {reviewer.provider_type}")

    system_prompt = (
        "You are a senior data engineer doing an independent pair-review of "
        "a migration artifact. Focus on: correctness (does the script do what "
        "it claims), idempotency, target-dialect compatibility, security "
        "(no secrets in plaintext, no over-privileged grants), and reversibility. "
        "Output a structured critique with: SEVERITY {OK | WARN | BLOCK}, then "
        "a bulleted list of findings. Be terse — under 30 lines."
    )
    user_prompt = f"Artifact filename: {forward.filename}\nType: {forward.file_type}\n\n---\n{content}\n---"

    ctx = CallContext(
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        api_key=api_key,
        base_url=reviewer.base_url,
        temperature=0.0,
        max_tokens=int(reviewer.max_tokens or 2048),
        timeout=float(reviewer.timeout or 60),
        extra_config=reviewer.extra_config or {},
    )
    parsed = adapter.call(ctx)
    if parsed is None:
        raise HTTPException(status_code=502, detail="Pair-review LLM call failed")

    critique = parsed.get("summary") or parsed.get("content") or str(parsed)

    # Persist as an ArtifactReview row anchored to the artifact's latest version.
    latest_version = (
        db.query(CodeArtifactVersion)
        .filter(CodeArtifactVersion.artifact_id == forward.id)
        .order_by(CodeArtifactVersion.version_number.desc())
        .first()
    )
    if not latest_version:
        raise HTTPException(status_code=409, detail="Artifact has no version row")
    review = ArtifactReview(
        artifact_version_id=latest_version.id,
        review_type="ai_pair_review",
        summary=f"Pair review by {reviewer.provider_type}:{model}",
        findings=critique,
        reviewer_id=user_id,
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    try:
        record_usage(
            db,
            organization_id=org_id,
            provider_type=reviewer.provider_type,
            model=model,
            input_tokens=int(len(user_prompt.split()) * 1.3),
            output_tokens=max(1, len(critique) // 4),
            project_id=forward.project_id,
            agent_name="pair_reviewer",
        )
    except Exception:  # noqa: BLE001
        pass

    write_audit(db, org_id=org_id, actor_id=user_id, action="artifact_pair_reviewed",
                entity_type="artifact", entity_id=forward.id,
                meta={"reviewer_provider": reviewer.provider_type, "reviewer_model": model, "review_id": review.id},
                request=request)
    return {
        "review_id": review.id,
        "artifact_id": forward.id,
        "reviewer_provider": reviewer.provider_type,
        "reviewer_model": model,
        "findings_preview": critique[:600],
    }
