"""Recon Agent — business-ready reconciliation plan + draft recon code.

The recon agent reasons over APPROVED context (project context, architecture,
validation evidence, connector metadata, sprint output) to produce:
  * a recon plan (recon-plan.md, stored as a MigrationArtifact), and
  * draft recon SQL/Python (GeneratedCodeArtifact rows — DRAFT, never executed
    against customer data by Helix; a developer reviews before running).

No row-level production source/target data is stored — only plans, code
templates and high-level summaries.
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.workspace import GeneratedCodeArtifact
from app.services import lifecycle_constants as LC
from app.services import stage_lifecycle_service as sl
from app.services import stage_agent_service as sa
from app.services import artifact_review_service as ar
from app.services import workspace_service as wsvc

_RECON_TYPES = [
    "schema recon", "row count recon", "checksum recon", "null count recon",
    "duplicate recon", "business-rule recon", "source-to-target aggregated recon",
    "file-to-table recon", "table-to-table recon",
]


def _recon_stage_id(db: Session, org_id: str, project_id: str) -> str | None:
    try:
        return sl._get_stage(db, org_id, project_id, LC.RECONCILIATION).id
    except HTTPException:
        return None


def _run_recon_agent(db: Session, org_id: str, project_id: str, focus: str) -> tuple[str, str]:
    """Run the recon agent (architect persona) over approved context with a
    recon-specific instruction. Returns (markdown, mode)."""
    from agents.runtime.bmad_executor import execute_agent_skill
    project = sl._get_project(db, org_id, project_id)
    base = sa._build_stage_prompt(db, org_id, project, LC.RECONCILIATION, None, None)
    requirement = f"{base}\n\n## Recon focus\n{focus}\n\nConsider these recon types where relevant: {', '.join(_RECON_TYPES)}."
    result = execute_agent_skill(
        agent_code="bmad-agent-architect", skill_name="bmad-create-architecture",
        project_id=project_id, requirement_text=requirement,
        output_model=sa._StageArtifactMeta, upstream_agents=None,
        org_id=org_id, artifact_filename="recon", persist_file=False,
    )
    if not result.success and not result.raw_text:
        raise HTTPException(status_code=502, detail="Recon agent failed: " + ("; ".join(result.errors) or "unknown error"))
    md = (result.artifact.body if result.artifact and result.artifact.body else result.raw_text) or ""
    return md, result.mode


def generate_recon_plan(db: Session, org_id: str, project_id: str, user_id: str):
    """Produce recon-plan.md and store it as a reviewable MigrationArtifact."""
    focus = ("Produce a thorough recon PLAN: the recon strategy, the specific checks to run "
             "(schema, row counts, checksums, null counts, duplicates, business rules, aggregates), "
             "the source/target scope, the report structure, and the business sign-off criteria.")
    md, mode = _run_recon_agent(db, org_id, project_id, focus)
    project = sl._get_project(db, org_id, project_id)
    artifact = ar.create_agent_artifact(
        db, org_id, project_id, _recon_stage_id(db, org_id, project_id),
        "recon-plan", f"Recon plan — {project.alias or project.name}", md, None, "recon",
    )
    sl._audit(db, org_id, user_id, "recon_plan_generated", project_id, LC.RECONCILIATION, f"mode={mode}")
    return artifact


def generate_recon_code(db: Session, org_id: str, project_id: str, user_id: str) -> list[GeneratedCodeArtifact]:
    """Produce DRAFT recon SQL/Python as GeneratedCodeArtifact rows. Never
    executed by Helix — a developer reviews before running."""
    focus = ("Generate DRAFT reconciliation CODE as fenced code blocks: SQL and/or Python templates "
             "that compare source vs target (row counts, checksums, null counts, duplicates, business "
             "rules, aggregates). Use clearly-marked placeholders for connection details — never embed "
             "credentials. Mark everything as draft to be reviewed before running.")
    md, mode = _run_recon_agent(db, org_id, project_id, focus)
    files = wsvc._extract_code_files(md, "recon")
    if not files:
        files = [{"file_name": "recon-notes.md", "file_type": "md", "language": "markdown", "content": md}]
    rows: list[GeneratedCodeArtifact] = []
    for f in files:
        rows.append(GeneratedCodeArtifact(
            organization_id=org_id, project_id=project_id, sprint_id=None,
            file_name=f"recon-{f['file_name']}", file_type=f["file_type"], language=f["language"],
            content=f["content"], status="draft", generated_by_agent="recon",
        ))
    db.add_all(rows)
    db.commit()
    for r in rows:
        db.refresh(r)
    sl._audit(db, org_id, user_id, "recon_code_generated", project_id, LC.RECONCILIATION, f"files={len(rows)} mode={mode}")
    return rows
