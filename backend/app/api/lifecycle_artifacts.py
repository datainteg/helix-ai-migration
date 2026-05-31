"""Markdown-artifact review API (migration_artifacts).

Namespaced under /migration-artifacts so it never collides with the file-based
/artifacts (code_artifacts) endpoints. RBAC: create-version/submit needs
project:write; approve/reject/request-changes needs agent:approve; comments +
reads need an authenticated org member.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.jwt import get_current_user_id
from app.auth.dependencies import get_current_organization_id, require_permission
from app.services.project_service import ensure_project_access
from app.services import artifact_review_service as svc
from app.schemas.lifecycle import (
    ArtifactVersionCreate, ArtifactReviewAction, ArtifactRejectAction, ArtifactCommentCreate,
    artifact_to_dict, version_to_dict, comment_to_dict,
)

router = APIRouter(tags=["lifecycle-artifacts"])


@router.get("/projects/{project_id}/migration-artifacts")
def list_artifacts(project_id: str, org_id: str = Depends(get_current_organization_id), user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    ensure_project_access(db, org_id, project_id)
    return [artifact_to_dict(a) for a in svc.list_project_artifacts(db, org_id, project_id)]


@router.get("/migration-artifacts/{artifact_id}")
def get_artifact(artifact_id: str, org_id: str = Depends(get_current_organization_id), user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return artifact_to_dict(svc.get_artifact(db, org_id, artifact_id))


@router.get("/migration-artifacts/{artifact_id}/versions")
def get_versions(artifact_id: str, org_id: str = Depends(get_current_organization_id), user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return [version_to_dict(v) for v in svc.get_artifact_versions(db, org_id, artifact_id)]


@router.post("/migration-artifacts/{artifact_id}/versions", status_code=201)
def create_version(artifact_id: str, data: ArtifactVersionCreate, org_id: str = Depends(get_current_organization_id), user_id: str = Depends(require_permission("project:write")), db: Session = Depends(get_db)):
    # A user-authored edit → new version (never overwrites the prior one).
    v = svc.edit_artifact_version(db, org_id, artifact_id, data.base_version_id, data.content_markdown or "", user_id, data.change_summary)
    return version_to_dict(v)


@router.post("/migration-artifacts/{artifact_id}/submit-review")
def submit_review(artifact_id: str, data: ArtifactReviewAction, org_id: str = Depends(get_current_organization_id), user_id: str = Depends(require_permission("project:write")), db: Session = Depends(get_db)):
    return artifact_to_dict(svc.submit_artifact_for_review(db, org_id, artifact_id, data.version_id, user_id))


@router.post("/migration-artifacts/{artifact_id}/approve")
def approve(artifact_id: str, data: ArtifactReviewAction, org_id: str = Depends(get_current_organization_id), user_id: str = Depends(require_permission("agent:approve")), db: Session = Depends(get_db)):
    return artifact_to_dict(svc.approve_artifact(db, org_id, artifact_id, data.version_id, user_id, data.comment))


@router.post("/migration-artifacts/{artifact_id}/reject")
def reject(artifact_id: str, data: ArtifactRejectAction, org_id: str = Depends(get_current_organization_id), user_id: str = Depends(require_permission("agent:approve")), db: Session = Depends(get_db)):
    return artifact_to_dict(svc.reject_artifact(db, org_id, artifact_id, data.version_id, user_id, data.comment))


@router.post("/migration-artifacts/{artifact_id}/request-changes")
def request_changes(artifact_id: str, data: ArtifactRejectAction, org_id: str = Depends(get_current_organization_id), user_id: str = Depends(require_permission("agent:approve")), db: Session = Depends(get_db)):
    return artifact_to_dict(svc.request_artifact_changes(db, org_id, artifact_id, data.version_id, user_id, data.comment))


@router.post("/migration-artifacts/{artifact_id}/comments", status_code=201)
def add_comment(artifact_id: str, data: ArtifactCommentCreate, org_id: str = Depends(get_current_organization_id), user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return comment_to_dict(svc.add_artifact_comment(db, org_id, artifact_id, data.version_id, user_id, data.comment))


@router.get("/migration-artifacts/{artifact_id}/comments")
def get_comments(artifact_id: str, org_id: str = Depends(get_current_organization_id), user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return [comment_to_dict(c) for c in svc.get_artifact_comments(db, org_id, artifact_id)]


@router.get("/migration-artifacts/{artifact_id}/compare")
def compare(artifact_id: str, from_version: int = Query(...), to_version: int = Query(...), org_id: str = Depends(get_current_organization_id), user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return svc.compare_artifact_versions(db, org_id, artifact_id, from_version, to_version)
