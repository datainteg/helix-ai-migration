import hashlib

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db
from app.auth.jwt import get_current_user_id
from app.models.artifacts import CodeArtifact, CodeArtifactVersion, ArtifactApproval
from app.services.auth_service import get_current_user
from app.storage.local import build_safe_artifact_path, save_file
from app.api.audit import write_audit

router = APIRouter(tags=["conversions"])


class ConversionStart(BaseModel):
    target_type: str = "databricks_notebook"


@router.post("/artifacts/{artifact_id}/convert")
def start_conversion(request: Request, artifact_id: str, data: ConversionStart, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Start draft code conversion. Generated output remains draft until approved."""
    org_id = get_current_user(db, user_id).memberships[0].organization_id
    version = (
        db.query(CodeArtifactVersion)
        .join(CodeArtifact, CodeArtifactVersion.artifact_id == CodeArtifact.id)
        .filter(CodeArtifactVersion.artifact_id == artifact_id, CodeArtifact.organization_id == org_id)
        .order_by(CodeArtifactVersion.version_number.desc())
        .first()
    )
    if not version:
        raise HTTPException(status_code=404, detail="No versions found")

    # Placeholder draft content — Code Migration Agent not yet wired
    draft_content = f"# Draft conversion to {data.target_type}\n# Generated from {artifact_id}\n# TODO: wire Code Migration Agent\n".encode()
    content_hash = hashlib.sha256(draft_content).hexdigest()

    next_version = str(int(version.version_number) + 1)
    storage_path = build_safe_artifact_path(artifact_id, f"draft_v{next_version}.py")
    save_file(storage_path, draft_content)

    draft_version = CodeArtifactVersion(
        artifact_id=artifact_id,
        version_number=next_version,
        content_hash=content_hash,
        storage_path=str(storage_path),
        generated_by_agent="code_migration",
        change_summary=f"Converted to {data.target_type}",
        approval_status="draft",
    )
    db.add(draft_version)
    db.commit()
    db.refresh(draft_version)
    write_audit(db, org_id=org_id, actor_id=user_id, action="artifact_conversion_started", entity_type="artifact_version", entity_id=draft_version.id, meta={"target_type": data.target_type}, request=request)
    return {"conversion_run_id": draft_version.id, "status": "draft", "message": "Generated draft ready for review"}


@router.post("/artifact-versions/{version_id}/approve")
def approve_version(request: Request, version_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    org_id = get_current_user(db, user_id).memberships[0].organization_id
    version = (
        db.query(CodeArtifactVersion)
        .join(CodeArtifact, CodeArtifactVersion.artifact_id == CodeArtifact.id)
        .filter(CodeArtifactVersion.id == version_id, CodeArtifact.organization_id == org_id)
        .first()
    )
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    version.approval_status = "approved"
    version.approved_by = user_id
    approval = ArtifactApproval(artifact_version_id=version_id, decision="approved", notes="Approved via API", approved_by=user_id)
    db.add(approval)
    db.commit()
    write_audit(db, org_id=org_id, actor_id=user_id, action="artifact_version_approved", entity_type="artifact_version", entity_id=version_id, request=request)
    return {"status": "approved", "version_id": version_id}


@router.post("/artifact-versions/{version_id}/reject")
def reject_version(request: Request, version_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    org_id = get_current_user(db, user_id).memberships[0].organization_id
    version = (
        db.query(CodeArtifactVersion)
        .join(CodeArtifact, CodeArtifactVersion.artifact_id == CodeArtifact.id)
        .filter(CodeArtifactVersion.id == version_id, CodeArtifact.organization_id == org_id)
        .first()
    )
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    version.approval_status = "rejected"
    approval = ArtifactApproval(artifact_version_id=version_id, decision="rejected", notes="Rejected via API", approved_by=user_id)
    db.add(approval)
    db.commit()
    write_audit(db, org_id=org_id, actor_id=user_id, action="artifact_version_rejected", entity_type="artifact_version", entity_id=version_id, request=request)
    return {"status": "rejected", "version_id": version_id}
