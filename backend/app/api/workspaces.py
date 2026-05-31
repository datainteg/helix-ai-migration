"""Developer workspace + generated-code API.

RBAC: workspace lifecycle + code generation/create/review need project:write;
final code approval needs agent:approve. Org/project isolation + audit are
enforced in the service layer. No generated code is ever executed here.
"""
from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.dependencies import get_current_organization_id, require_permission
from app.services.project_service import ensure_project_access
from app.services import workspace_service as svc

router = APIRouter(tags=["workspaces"])


# ── Bodies ───────────────────────────────────────────────────────────
class WorkspaceCreate(BaseModel):
    workspace_type: str = "artifact_only"
    sprint_id: str | None = None


class GeneratedCodeCreate(BaseModel):
    file_name: str = Field(max_length=255)
    file_type: str | None = None
    language: str | None = None
    content: str | None = None
    sprint_id: str | None = None
    stage_id: str | None = None
    artifact_id: str | None = None
    generated_by_agent: str | None = None


class GenerateRequest(BaseModel):
    sprint_id: str | None = None
    instructions: str | None = Field(default=None, max_length=4000)


class CodeReviewRequest(BaseModel):
    decision: str = "reviewed"   # reviewed | rejected


# ── Serializers ──────────────────────────────────────────────────────
def _ws(w) -> dict:
    return {
        "id": w.id, "project_id": w.project_id, "sprint_id": w.sprint_id,
        "workspace_alias": w.workspace_alias, "status": w.status, "workspace_type": w.workspace_type,
        "container_name": w.container_name, "workspace_url": w.workspace_url,
        "storage_path": w.storage_path, "created_by_user_id": w.created_by_user_id,
        "created_at": str(w.created_at) if w.created_at else None,
    }


def _code(c) -> dict:
    return {
        "id": c.id, "project_id": c.project_id, "sprint_id": c.sprint_id, "stage_id": c.stage_id,
        "artifact_id": c.artifact_id, "file_name": c.file_name, "file_type": c.file_type,
        "language": c.language, "content": c.content, "status": c.status,
        "generated_by_agent": c.generated_by_agent, "reviewed_by_user_id": c.reviewed_by_user_id,
        "created_at": str(c.created_at) if c.created_at else None,
    }


# ── Workspaces ───────────────────────────────────────────────────────
@router.post("/projects/{project_id}/workspaces", status_code=201)
def create_workspace(project_id: str, data: WorkspaceCreate = Body(default=WorkspaceCreate()),
                     org_id: str = Depends(get_current_organization_id),
                     user_id: str = Depends(require_permission("project:write")), db: Session = Depends(get_db)):
    ensure_project_access(db, org_id, project_id)
    return _ws(svc.create_workspace(db, org_id, project_id, user_id, data.workspace_type, data.sprint_id))


@router.get("/projects/{project_id}/workspaces")
def list_workspaces(project_id: str, org_id: str = Depends(get_current_organization_id),
                    user_id: str = Depends(require_permission("project:read")), db: Session = Depends(get_db)):
    ensure_project_access(db, org_id, project_id)
    return [_ws(w) for w in svc.list_workspaces(db, org_id, project_id)]


@router.get("/workspaces/{workspace_id}")
def get_workspace(workspace_id: str, org_id: str = Depends(get_current_organization_id),
                  user_id: str = Depends(require_permission("project:read")), db: Session = Depends(get_db)):
    return _ws(svc.get_workspace(db, org_id, workspace_id))


@router.post("/workspaces/{workspace_id}/start")
def start_workspace(workspace_id: str, org_id: str = Depends(get_current_organization_id),
                    user_id: str = Depends(require_permission("project:write")), db: Session = Depends(get_db)):
    return _ws(svc.start_workspace(db, org_id, workspace_id, user_id))


@router.post("/workspaces/{workspace_id}/stop")
def stop_workspace(workspace_id: str, org_id: str = Depends(get_current_organization_id),
                   user_id: str = Depends(require_permission("project:write")), db: Session = Depends(get_db)):
    return _ws(svc.stop_workspace(db, org_id, workspace_id, user_id))


@router.post("/workspaces/{workspace_id}/sync-artifacts")
def sync_artifacts(workspace_id: str, org_id: str = Depends(get_current_organization_id),
                   user_id: str = Depends(require_permission("project:write")), db: Session = Depends(get_db)):
    return svc.sync_artifacts(db, org_id, workspace_id)


# ── Generated code ───────────────────────────────────────────────────
@router.post("/projects/{project_id}/generated-code", status_code=201)
def create_generated_code(project_id: str, data: GeneratedCodeCreate,
                          org_id: str = Depends(get_current_organization_id),
                          user_id: str = Depends(require_permission("project:write")), db: Session = Depends(get_db)):
    ensure_project_access(db, org_id, project_id)
    return _code(svc.create_generated_code(db, org_id, project_id, user_id, data.model_dump()))


@router.post("/projects/{project_id}/generated-code/generate", status_code=201)
def generate_code(project_id: str, data: GenerateRequest = Body(default=GenerateRequest()),
                  org_id: str = Depends(get_current_organization_id),
                  user_id: str = Depends(require_permission("project:write")), db: Session = Depends(get_db)):
    """Run Amelia over approved artifacts and persist each code block as a draft."""
    ensure_project_access(db, org_id, project_id)
    rows = svc.generate_code(db, org_id, project_id, user_id, data.sprint_id, data.instructions)
    return {"created": len(rows), "files": [_code(r) for r in rows]}


@router.get("/projects/{project_id}/generated-code")
def list_generated_code(project_id: str, org_id: str = Depends(get_current_organization_id),
                        user_id: str = Depends(require_permission("project:read")), db: Session = Depends(get_db)):
    ensure_project_access(db, org_id, project_id)
    return [_code(c) for c in svc.list_generated_code(db, org_id, project_id)]


@router.post("/generated-code/{code_id}/review")
def review_generated_code(code_id: str, data: CodeReviewRequest,
                          org_id: str = Depends(get_current_organization_id),
                          user_id: str = Depends(require_permission("project:write")), db: Session = Depends(get_db)):
    return _code(svc.review_generated_code(db, org_id, code_id, user_id, data.decision))


@router.post("/generated-code/{code_id}/approve")
def approve_generated_code(code_id: str, org_id: str = Depends(get_current_organization_id),
                           user_id: str = Depends(require_permission("agent:approve")), db: Session = Depends(get_db)):
    return _code(svc.approve_generated_code(db, org_id, code_id, user_id))
