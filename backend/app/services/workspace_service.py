"""Developer workspace + generated-code service.

Generated code is ALWAYS draft until reviewed/approved and is NEVER executed in
the backend. code-server is optional and runs in an isolated per-project
container provisioned by an operator (the backend only tracks workspace
metadata + URLs — it does not spawn Docker or run any code).

Code generation reuses Amelia (bmad-agent-dev) over the project's APPROVED
artifacts (architecture, plan, …) and splits fenced code blocks into individual
GeneratedCodeArtifact rows.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.workspace import DeveloperWorkspace, GeneratedCodeArtifact
from app.models.project import Project
from app.services import lifecycle_constants as LC
from app.services import stage_lifecycle_service as sl
from app.services import stage_agent_service as sa


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_project(db: Session, org_id: str, project_id: str) -> Project:
    return sl._get_project(db, org_id, project_id)


# ── Workspaces ───────────────────────────────────────────────────────
def _workspace_alias(project: Project, n: int) -> str:
    base = project.alias or project.slug or project.id[:8]
    return f"{base}-WS{n}"


def create_workspace(db: Session, org_id: str, project_id: str, user_id: str,
                     workspace_type: str = "artifact_only", sprint_id: str | None = None) -> DeveloperWorkspace:
    if workspace_type not in ("code_server", "external", "artifact_only"):
        raise HTTPException(status_code=422, detail="Invalid workspace_type.")
    project = _get_project(db, org_id, project_id)
    n = db.query(DeveloperWorkspace).filter(DeveloperWorkspace.project_id == project_id).count() + 1
    alias = _workspace_alias(project, n)
    ws = DeveloperWorkspace(
        organization_id=org_id, project_id=project_id, sprint_id=sprint_id,
        workspace_alias=alias, status="created", workspace_type=workspace_type,
        # Per-project workspace folder; the backend never writes/executes here —
        # an operator-provisioned code-server container mounts it read/write.
        storage_path=f"/workspaces/{alias}",
        created_by_user_id=user_id,
    )
    db.add(ws)
    db.commit()
    db.refresh(ws)
    return ws


def list_workspaces(db: Session, org_id: str, project_id: str) -> list[DeveloperWorkspace]:
    return (
        db.query(DeveloperWorkspace)
        .filter(DeveloperWorkspace.organization_id == org_id, DeveloperWorkspace.project_id == project_id)
        .order_by(DeveloperWorkspace.created_at.desc())
        .all()
    )


def get_workspace(db: Session, org_id: str, workspace_id: str) -> DeveloperWorkspace:
    ws = db.query(DeveloperWorkspace).filter(
        DeveloperWorkspace.id == workspace_id, DeveloperWorkspace.organization_id == org_id
    ).first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


def start_workspace(db: Session, org_id: str, workspace_id: str, user_id: str) -> DeveloperWorkspace:
    ws = get_workspace(db, org_id, workspace_id)
    if ws.workspace_type == "code_server":
        # The backend does NOT spawn containers. code-server must be provisioned
        # out-of-band via the optional compose profile; we record the expected
        # container name + URL so the operator/UI can wire it up.
        if os.getenv("HELIX_CODE_SERVER_ENABLED", "").lower() not in ("1", "true", "yes"):
            raise HTTPException(status_code=409, detail="code-server is not enabled on this deployment (set HELIX_CODE_SERVER_ENABLED + provision the compose profile).")
        ws.container_name = f"helix-workspace-{ws.workspace_alias}"
        base = os.getenv("HELIX_CODE_SERVER_BASE_URL", "").rstrip("/")
        ws.workspace_url = f"{base}/{ws.workspace_alias}/" if base else None
    ws.status = "running"
    db.commit()
    db.refresh(ws)
    return ws


def stop_workspace(db: Session, org_id: str, workspace_id: str, user_id: str) -> DeveloperWorkspace:
    ws = get_workspace(db, org_id, workspace_id)
    ws.status = "stopped"
    db.commit()
    db.refresh(ws)
    return ws


def sync_artifacts(db: Session, org_id: str, workspace_id: str) -> dict:
    """Report the generated-code artifacts visible to this workspace's project.
    Metadata-only — no filesystem mutation, no execution."""
    ws = get_workspace(db, org_id, workspace_id)
    rows = list_generated_code(db, org_id, ws.project_id)
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r.status] = by_status.get(r.status, 0) + 1
    return {"workspace_id": ws.id, "generated_code_count": len(rows), "by_status": by_status}


# ── Generated code ───────────────────────────────────────────────────
_FENCE = re.compile(r"```([a-zA-Z0-9_+.\-]*)\s*\n(.*?)```", re.DOTALL)
_EXT = {"python": "py", "py": "py", "sql": "sql", "yaml": "yml", "yml": "yml",
        "json": "json", "bash": "sh", "sh": "sh", "markdown": "md", "md": "md",
        "dockerfile": "Dockerfile", "hcl": "tf", "scala": "scala", "java": "java"}
_FILE_TYPE = {"py": "python", "python": "python", "sql": "sql", "yml": "yaml", "yaml": "yaml",
              "ipynb": "notebook", "md": "md", "py-dag": "dag"}


def _classify(lang: str, body: str) -> tuple[str, str]:
    """Return (file_type, language)."""
    lang = (lang or "").lower()
    if "airflow" in body.lower() and ("dag(" in body.lower() or "with dag" in body.lower()):
        return "dag", "python"
    if lang in ("python", "py"):
        return "python", "python"
    if lang == "sql":
        return "sql", "sql"
    if lang in ("yaml", "yml"):
        return "yaml", "yaml"
    if lang in ("md", "markdown"):
        return "md", "markdown"
    return (lang or "code"), (lang or "text")


def _extract_code_files(markdown: str, agent: str) -> list[dict]:
    files: list[dict] = []
    for i, m in enumerate(_FENCE.finditer(markdown or ""), start=1):
        lang = (m.group(1) or "").strip()
        body = m.group(2).strip()
        if not body or len(body) < 10:
            continue
        file_type, language = _classify(lang, body)
        ext = _EXT.get(lang.lower(), "txt")
        files.append({
            "file_name": f"{file_type}-{i}.{ext}",
            "file_type": file_type, "language": language, "content": body,
        })
    return files


def create_generated_code(db: Session, org_id: str, project_id: str, user_id: str, data: dict) -> GeneratedCodeArtifact:
    _get_project(db, org_id, project_id)
    row = GeneratedCodeArtifact(
        organization_id=org_id, project_id=project_id,
        sprint_id=data.get("sprint_id"), stage_id=data.get("stage_id"), artifact_id=data.get("artifact_id"),
        file_name=str(data.get("file_name") or "snippet.txt")[:255],
        file_type=data.get("file_type"), language=data.get("language"),
        content=data.get("content"), status="draft",
        generated_by_agent=data.get("generated_by_agent"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def generate_code(db: Session, org_id: str, project_id: str, user_id: str,
                  sprint_id: str | None = None, instructions: str | None = None) -> list[GeneratedCodeArtifact]:
    """Run Amelia over the approved architecture/plan context and persist each
    fenced code block as a DRAFT GeneratedCodeArtifact. Never executed."""
    from agents.runtime.bmad_executor import execute_agent_skill
    project = _get_project(db, org_id, project_id)
    requirement = sa._build_stage_prompt(db, org_id, project, LC.DEVELOPMENT, None, instructions)
    result = execute_agent_skill(
        agent_code="bmad-agent-dev", skill_name="bmad-dev-story",
        project_id=project_id, requirement_text=requirement,
        output_model=sa._StageArtifactMeta, upstream_agents=None,
        org_id=org_id, artifact_filename="generated-code", persist_file=False,
    )
    if not result.success and not result.raw_text:
        raise HTTPException(status_code=502, detail="Code generation failed: " + ("; ".join(result.errors) or "unknown error"))
    markdown = (result.artifact.body if result.artifact and result.artifact.body else result.raw_text) or ""
    files = _extract_code_files(markdown, "bmad-agent-dev")
    if not files:
        # No fenced code — keep the whole plan as a single markdown draft so the
        # output is never silently lost.
        files = [{"file_name": "implementation-notes.md", "file_type": "md", "language": "markdown", "content": markdown}]
    rows: list[GeneratedCodeArtifact] = []
    for f in files:
        rows.append(GeneratedCodeArtifact(
            organization_id=org_id, project_id=project_id, sprint_id=sprint_id,
            file_name=f["file_name"], file_type=f["file_type"], language=f["language"],
            content=f["content"], status="draft", generated_by_agent="bmad-agent-dev",
        ))
    db.add_all(rows)
    db.commit()
    for r in rows:
        db.refresh(r)
    sl._audit(db, org_id, user_id, "code_generated", project_id, LC.DEVELOPMENT, f"files={len(rows)} mode={result.mode}")
    return rows


def list_generated_code(db: Session, org_id: str, project_id: str) -> list[GeneratedCodeArtifact]:
    return (
        db.query(GeneratedCodeArtifact)
        .filter(GeneratedCodeArtifact.organization_id == org_id, GeneratedCodeArtifact.project_id == project_id)
        .order_by(GeneratedCodeArtifact.created_at.desc())
        .all()
    )


def _get_code(db: Session, org_id: str, code_id: str) -> GeneratedCodeArtifact:
    row = db.query(GeneratedCodeArtifact).filter(
        GeneratedCodeArtifact.id == code_id, GeneratedCodeArtifact.organization_id == org_id
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Generated code not found")
    return row


def review_generated_code(db: Session, org_id: str, code_id: str, user_id: str, decision: str) -> GeneratedCodeArtifact:
    """decision: reviewed | rejected."""
    if decision not in ("reviewed", "rejected"):
        raise HTTPException(status_code=422, detail="decision must be 'reviewed' or 'rejected'.")
    row = _get_code(db, org_id, code_id)
    row.status = decision
    row.reviewed_by_user_id = user_id
    db.commit()
    db.refresh(row)
    return row


def approve_generated_code(db: Session, org_id: str, code_id: str, user_id: str) -> GeneratedCodeArtifact:
    row = _get_code(db, org_id, code_id)
    row.status = "approved"
    row.reviewed_by_user_id = user_id
    db.commit()
    db.refresh(row)
    return row
