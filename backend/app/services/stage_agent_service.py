"""Stage-gated agent execution.

Each lifecycle stage runs as a SHORT, synchronous agent call (reusing the
existing BMAD executor + personas) — NOT a long-lived Temporal workflow. The DB
state machine in `stage_lifecycle_service` is the source of truth; this service
only:

  1. validates the stage is agent-runnable and the prior required stage is done,
  2. builds the stage prompt from project metadata + the latest approved
     requirement + previously APPROVED artifacts (+ connector/sprint metadata),
  3. runs the mapped persona via `execute_agent_skill` (cost recorded there),
  4. stores the output as a migration_artifact version, and
  5. drives the stage to generated → under_review.

The legacy HelixBMAD workflow remains available untouched as a fallback.

Security: connector SECRETS are never put in a prompt — only the connector
type/name and the masked (redacted) config preview. Only APPROVED artifacts are
used as context (per spec), so unreviewed agent output never silently feeds the
next stage.
"""
from __future__ import annotations

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.models.project import Project, MigrationRequirement, SourceConnection, TargetConnection
from app.models.migration_artifact import MigrationArtifact, MigrationArtifactVersion
from app.models.sprint import Sprint
from app.services import lifecycle_constants as LC
from app.services import stage_lifecycle_service as sl
from app.services import artifact_review_service as ar


# ── Stage → (persona, skill) execution map ───────────────────────────
# Reuses existing BMAD personas + skills (verified present on disk). Stages
# whose lifecycle agent is a sentinel (__orchestration__/__human__/__system__)
# are NOT agent-runnable and are handled by later prompts (sprint exec, sign-off,
# closure).
STAGE_EXECUTION: dict[str, tuple[str, str]] = {
    LC.PROJECT_CONTEXT:   ("bmad-agent-architect",   "bmad-generate-project-context"),
    LC.BUSINESS_ANALYSIS: ("bmad-agent-analyst",     "bmad-product-brief"),
    LC.ARCHITECTURE:      ("bmad-agent-architect",   "bmad-create-architecture"),
    LC.PROJECT_PLANNING:  ("bmad-agent-pm",          "bmad-prd"),
    LC.UX_DESIGN:         ("bmad-agent-ux-designer", "bmad-create-ux-design"),
    LC.SPRINT_GENERATION: ("bmad-agent-pm",          "bmad-sprint-planning"),
    LC.DEVELOPMENT:       ("bmad-agent-dev",         "bmad-dev-story"),
    LC.VALIDATION:        ("bmad-agent-dev",         "bmad-qa-generate-e2e-tests"),
    LC.RECONCILIATION:    ("bmad-agent-architect",   "bmad-create-architecture"),
    LC.DOCUMENTATION:     ("bmad-agent-tech-writer", "bmad-document-project"),
}

# What each stage's document must contain (verbatim from the Prompt-3 spec).
STAGE_PRODUCE: dict[str, list[str]] = {
    LC.PROJECT_CONTEXT:   ["migration objective", "source systems", "target systems", "scope",
                           "assumptions", "constraints", "risks", "open questions", "initial execution strategy"],
    LC.BUSINESS_ANALYSIS: ["business requirements", "use cases", "stakeholders", "acceptance criteria",
                           "data domains", "risks", "success metrics"],
    LC.ARCHITECTURE:      ["source-target architecture", "migration architecture", "connector plan",
                           "schema discovery strategy", "validation strategy", "recon strategy",
                           "security/governance", "deployment approach"],
    LC.PROJECT_PLANNING:  ["epics", "stories", "milestones", "dependencies", "timeline",
                           "resource assumptions", "risks"],
    LC.UX_DESIGN:         ["user journeys", "key screens", "interaction notes", "accessibility considerations"],
    LC.SPRINT_GENERATION: ["sprint list", "sprint goals", "tasks", "owners", "dependencies",
                           "validation/recon checkpoints", "approval gates"],
    LC.DEVELOPMENT:       ["implementation plan", "generated code or code skeletons", "testing instructions",
                           "known assumptions", "files created"],
    LC.VALIDATION:        ["test cases", "expected validation evidence", "validation checklist", "pass/fail criteria"],
    LC.RECONCILIATION:    ["recon strategy", "recon checks", "recon SQL/Python code", "report structure",
                           "business sign-off criteria"],
    LC.DOCUMENTATION:     ["runbook", "technical documentation", "business summary", "closure checklist"],
}

_MAX_ARTIFACT_CHARS = 6000          # cap each prior artifact fed into the prompt
_NON_AGENT_SENTINELS = {"__orchestration__", "__human__", "__system__"}


class _StageArtifactMeta(BaseModel):
    """Permissive output contract — the BMAD executor validates frontmatter
    against this. All fields optional so any reasonable agent output parses;
    the markdown body is what we persist."""

    model_config = ConfigDict(extra="allow")
    title: str | None = None
    summary: str | None = None


def is_agent_runnable(stage_key: str) -> bool:
    return stage_key in STAGE_EXECUTION


# ── Context building ─────────────────────────────────────────────────
def _latest_requirement(db: Session, project_id: str) -> MigrationRequirement | None:
    q = db.query(MigrationRequirement).filter(MigrationRequirement.project_id == project_id)
    approved = q.filter(MigrationRequirement.status == "approved").order_by(MigrationRequirement.created_at.desc()).first()
    return approved or q.order_by(MigrationRequirement.created_at.desc()).first()


def _approved_artifacts_context(db: Session, org_id: str, project_id: str, exclude_stage_id: str | None) -> str:
    """Markdown of every APPROVED artifact for the project (the reviewed,
    possibly user-edited content) — the only artifact context a stage uses."""
    rows = (
        db.query(MigrationArtifact)
        .filter(
            MigrationArtifact.organization_id == org_id,
            MigrationArtifact.project_id == project_id,
            MigrationArtifact.status == "approved",
        )
        .order_by(MigrationArtifact.created_at)
        .all()
    )
    blocks: list[str] = []
    for a in rows:
        if exclude_stage_id and a.stage_id == exclude_stage_id:
            continue
        ver = db.query(MigrationArtifactVersion).filter(MigrationArtifactVersion.id == a.current_version_id).first()
        body = (ver.content_markdown if ver and ver.content_markdown else "") or ""
        if len(body) > _MAX_ARTIFACT_CHARS:
            body = body[:_MAX_ARTIFACT_CHARS] + "\n…(truncated)…"
        blocks.append(f"### Approved: {a.title} ({a.artifact_type})\n{body}")
    return "\n\n".join(blocks)


def _connector_context(db: Session, org_id: str, project_id: str) -> str:
    """Connector type/name + masked preview only — never the secret config."""
    src = db.query(SourceConnection).filter(SourceConnection.project_id == project_id, SourceConnection.organization_id == org_id).all()
    tgt = db.query(TargetConnection).filter(TargetConnection.project_id == project_id, TargetConnection.organization_id == org_id).all()
    lines: list[str] = []
    for c in src:
        lines.append(f"- SOURCE: {c.name} [{c.connector_type}] {c.config_masked or ''}".rstrip())
    for c in tgt:
        lines.append(f"- TARGET: {c.name} [{c.connector_type}] {c.config_masked or ''}".rstrip())
    return "\n".join(lines)


def _sprint_context(db: Session, org_id: str, project_id: str) -> str:
    rows = (
        db.query(Sprint)
        .filter(Sprint.project_id == project_id, Sprint.organization_id == org_id)
        .order_by(Sprint.index)
        .all()
    )
    return "\n".join(f"- Sprint {s.index}: {s.name} — {s.status} — {(s.goal or '')[:200]}" for s in rows)


def _build_stage_prompt(db: Session, org_id: str, project: Project, stage_key: str,
                        stage_id: str | None, extra_instructions: str | None) -> str:
    """Assemble the full stage requirement_text fed to the persona."""
    parts: list[str] = []
    parts.append(
        f"# Migration project: {project.alias or project.name}\n"
        f"- Name: {project.name}\n"
        f"- Type: {getattr(project, 'migration_type', None) or 'db_to_db'}\n"
        f"- Environment: {getattr(project, 'environment', None) or 'n/a'}\n"
        f"- Risk level: {getattr(project, 'risk_level', None) or 'n/a'}\n"
        f"- Description: {project.description or 'n/a'}"
    )

    req = _latest_requirement(db, project.id)
    if req and req.source_text:
        parts.append(f"## Approved requirement (v{req.version}, {req.status})\n{req.source_text[:_MAX_ARTIFACT_CHARS]}")

    conn = _connector_context(db, org_id, project.id)
    if conn:
        parts.append(f"## Connectors\n{conn}")

    prior = _approved_artifacts_context(db, org_id, project.id, exclude_stage_id=stage_id)
    if prior:
        parts.append(f"## Previously approved artifacts (authoritative context)\n{prior}")

    sprints = _sprint_context(db, org_id, project.id)
    if sprints:
        parts.append(f"## Sprints\n{sprints}")

    produce = STAGE_PRODUCE.get(stage_key, [])
    if produce:
        bullets = "\n".join(f"- {p}" for p in produce)
        parts.append(
            f"## Your task for the {LC.STAGE_NAME_BY_KEY.get(stage_key, stage_key)} stage\n"
            f"Produce a thorough, enterprise-grade Markdown document covering:\n{bullets}\n\n"
            f"Use the approved context above as the authoritative source. Be concrete and migration-specific; "
            f"do not invent connector credentials. Use clear `##` section headings matching the items above."
        )
    if extra_instructions:
        parts.append(f"## Additional reviewer instructions (address these)\n{extra_instructions.strip()}")

    return "\n\n".join(parts)


# ── Agent execution ──────────────────────────────────────────────────
def _run_persona(org_id: str, project_id: str, stage_key: str, requirement_text: str) -> tuple[str, str]:
    """Run the mapped persona synchronously. Returns (markdown, mode).

    Raises 502 only if the persona/skill could not be loaded at all (the
    executor itself always falls back to deterministic mock output otherwise,
    so a stage never stalls)."""
    from agents.runtime.bmad_executor import execute_agent_skill

    agent_code, skill_name = STAGE_EXECUTION[stage_key]
    result = execute_agent_skill(
        agent_code=agent_code,
        skill_name=skill_name,
        project_id=project_id,
        requirement_text=requirement_text,
        output_model=_StageArtifactMeta,
        upstream_agents=None,           # context is supplied explicitly from APPROVED DB artifacts
        org_id=org_id,
        artifact_filename=LC.STAGE_ARTIFACT_TYPE_BY_KEY.get(stage_key, stage_key.lower()),
        persist_file=False,             # DB is the source of truth; backend artifact volume is read-only
    )
    if not result.success and not result.raw_text:
        raise HTTPException(status_code=502, detail=f"Agent execution failed for {stage_key}: {'; '.join(result.errors) or 'unknown error'}")
    markdown = (result.artifact.body if result.artifact and result.artifact.body else result.raw_text) or ""
    return markdown, result.mode


def _resolve_runnable_stage(db: Session, org_id: str, project_id: str, stage_key: str):
    if not LC.is_valid_stage(stage_key):
        raise HTTPException(status_code=404, detail=f"Unknown stage {stage_key}")
    if not is_agent_runnable(stage_key):
        agent = LC.STAGE_AGENT_BY_KEY.get(stage_key)
        raise HTTPException(status_code=400, detail=f"Stage {stage_key} is not agent-runnable (agent={agent}); it is handled outside agent execution.")
    return sl._get_stage(db, org_id, project_id, stage_key)


def run_stage_agent(db: Session, org_id: str, project_id: str, stage_key: str,
                    user_id: str, instructions: str | None = None) -> dict:
    """First agent run for a stage: start (gating prior) → generate artifact v1
    → under_review. If the stage already has an artifact, this delegates to a
    regenerate (new version)."""
    stage = _resolve_runnable_stage(db, org_id, project_id, stage_key)
    if stage.status in LC.STAGE_DONE_STATUSES:
        raise HTTPException(status_code=409, detail=f"Stage {stage_key} is {stage.status}; reopen it before re-running the agent.")
    if stage.current_artifact_id:
        return regenerate_stage_agent(db, org_id, project_id, stage_key, user_id, instructions)

    project = sl._get_project(db, org_id, project_id)
    if stage.status == "not_started":
        sl.start_stage(db, org_id, project_id, stage_key, user_id)   # gates prior-required + sets running

    requirement_text = _build_stage_prompt(db, org_id, project, stage_key, stage.id, instructions)
    markdown, mode = _run_persona(org_id, project_id, stage_key, requirement_text)

    agent_code = STAGE_EXECUTION[stage_key][0]
    artifact = ar.create_agent_artifact(
        db, org_id, project_id, stage.id,
        LC.STAGE_ARTIFACT_TYPE_BY_KEY.get(stage_key, stage_key.lower()),
        f"{LC.STAGE_NAME_BY_KEY.get(stage_key, stage_key)} — {project.alias or project.name}",
        markdown, None, agent_code,
    )
    version_id = artifact.current_version_id
    sl.mark_stage_generated(db, org_id, project_id, stage_key, artifact.id, actor_type="agent", actor_id=agent_code)
    sl.submit_stage_for_review(db, org_id, project_id, stage_key, artifact.id, user_id)
    sl._audit(db, org_id, user_id, "run_agent", project_id, stage_key, f"agent={agent_code} mode={mode}")
    return {"stage_key": stage_key, "artifact_id": artifact.id, "version_id": version_id,
            "status": "under_review", "agent": agent_code, "mode": mode}


def regenerate_stage_agent(db: Session, org_id: str, project_id: str, stage_key: str,
                           user_id: str, instructions: str | None = None) -> dict:
    """Re-run the agent for a stage that already has an artifact → append a NEW
    version (never overwrites history) → back to under_review."""
    stage = _resolve_runnable_stage(db, org_id, project_id, stage_key)
    if not stage.current_artifact_id:
        raise HTTPException(status_code=409, detail=f"Stage {stage_key} has no artifact yet; call run-agent first.")
    if stage.status in LC.STAGE_DONE_STATUSES:
        raise HTTPException(status_code=409, detail=f"Stage {stage_key} is {stage.status}; reopen it before regenerating.")

    project = sl._get_project(db, org_id, project_id)
    requirement_text = _build_stage_prompt(db, org_id, project, stage_key, stage.id, instructions)
    markdown, mode = _run_persona(org_id, project_id, stage_key, requirement_text)

    agent_code = STAGE_EXECUTION[stage_key][0]
    version = ar.create_artifact_version(
        db, org_id, stage.current_artifact_id, markdown, None,
        created_by_type="agent", created_by_agent=agent_code, created_by_user_id=None,
        change_summary=f"Agent regeneration ({mode})" + (f" — {instructions[:120]}" if instructions else ""),
    )
    sl.mark_stage_generated(db, org_id, project_id, stage_key, stage.current_artifact_id, actor_type="agent", actor_id=agent_code)
    sl.submit_stage_for_review(db, org_id, project_id, stage_key, stage.current_artifact_id, user_id)
    sl._audit(db, org_id, user_id, "regenerate_agent", project_id, stage_key, f"agent={agent_code} mode={mode}")
    return {"stage_key": stage_key, "artifact_id": stage.current_artifact_id, "version_id": version.id,
            "status": "under_review", "agent": agent_code, "mode": mode}


def continue_after_approval(db: Session, org_id: str, project_id: str, stage_key: str, user_id: str) -> dict:
    """After a stage is approved, advance the pointer and — if the next stage is
    agent-runnable and untouched — kick off its agent automatically."""
    stage = sl._get_stage(db, org_id, project_id, stage_key)
    if stage.status not in LC.STAGE_DONE_STATUSES:
        raise HTTPException(status_code=409, detail=f"Stage {stage_key} is {stage.status}; it must be approved before continuing.")

    nxt = sl.advance_to_next_stage(db, org_id, project_id)
    if nxt is None:
        return {"completed": True, "next_stage": None, "auto_ran": False}

    if is_agent_runnable(nxt.stage_key) and nxt.status == "not_started":
        run = run_stage_agent(db, org_id, project_id, nxt.stage_key, user_id)
        return {"completed": False, "next_stage": nxt.stage_key, "auto_ran": True, "run": run}
    return {"completed": False, "next_stage": nxt.stage_key, "auto_ran": False,
            "stage": {"stage_key": nxt.stage_key, "status": nxt.status, "assigned_agent": nxt.assigned_agent}}
