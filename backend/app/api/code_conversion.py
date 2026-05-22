from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db
from app.auth.jwt import get_current_user_id
from app.models.artifacts import CodeArtifactVersion, ArtifactApproval

router = APIRouter(tags=["conversions"])


class ConversionStart(BaseModel):
    target_type: str = "databricks_notebook"


@router.post("/artifacts/{artifact_id}/convert")
def start_conversion(artifact_id: str, data: ConversionStart, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Start draft code conversion. Generated output remains draft until approved."""
    version = db.query(CodeArtifactVersion).filter(CodeArtifactVersion.artifact_id == artifact_id).order_by(CodeArtifactVersion.version_number.desc()).first()
    if not version:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="No versions found")

    # Create a generated draft version
    draft_version = CodeArtifactVersion(
        artifact_id=artifact_id,
        version_number=str(int(version.version_number) + 1),
        content_hash="generated_draft_hash",
        storage_path=f"/drafts/{artifact_id}/v{int(version.version_number) + 1}",
        generated_by_agent="code_migration",
        change_summary=f"Converted to {data.target_type}",
        approval_status="draft",
    )
    db.add(draft_version)
    db.commit()
    db.refresh(draft_version)
    return {"conversion_run_id": draft_version.id, "status": "draft", "message": "Generated draft ready for review"}


@router.post("/artifact-versions/{version_id}/approve")
def approve_version(version_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    version = db.query(CodeArtifactVersion).filter(CodeArtifactVersion.id == version_id).first()
    if not version:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Version not found")

    version.approval_status = "approved"
    version.approved_by = user_id
    approval = ArtifactApproval(artifact_version_id=version_id, decision="approved", notes="Approved via API", approved_by=user_id)
    db.add(approval)
    db.commit()
    return {"status": "approved", "version_id": version_id}


@router.post("/artifact-versions/{version_id}/reject")
def reject_version(version_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    version = db.query(CodeArtifactVersion).filter(CodeArtifactVersion.id == version_id).first()
    if not version:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Version not found")

    version.approval_status = "rejected"
    approval = ArtifactApproval(artifact_version_id=version_id, decision="rejected", notes="Rejected via API", approved_by=user_id)
    db.add(approval)
    db.commit()
    return {"status": "rejected", "version_id": version_id}
