import json
import os
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db
from app.auth.jwt import get_current_user_id
from app.models.artifacts import ArtifactReview, CodeArtifactVersion, CodeArtifact
from agents.code_analyzer_agent.analyzer import analyze_code
from agents.code_review_agent.reviewer import review_code

router = APIRouter(tags=["code-reviews"])


def _read_artifact_content(db: Session, artifact_id: str) -> tuple[str, str]:
    """Read actual artifact content from storage. Returns (content, filename)."""
    artifact = db.query(CodeArtifact).filter(CodeArtifact.id == artifact_id).first()
    if not artifact:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Artifact not found")

    path = artifact.storage_path
    if not os.path.exists(path):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Artifact file not found on storage")

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    return content, artifact.filename


def _get_latest_version(db: Session, artifact_id: str) -> CodeArtifactVersion:
    version = db.query(CodeArtifactVersion).filter(
        CodeArtifactVersion.artifact_id == artifact_id
    ).order_by(CodeArtifactVersion.version_number.desc()).first()
    if not version:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="No versions found")
    return version


@router.post("/artifacts/{artifact_id}/analyze")
def analyze_artifact(artifact_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    version = _get_latest_version(db, artifact_id)
    content, filename = _read_artifact_content(db, artifact_id)

    result = analyze_code(content, filename)
    review = ArtifactReview(
        artifact_version_id=version.id,
        review_type="analysis",
        summary=result.summary,
        findings=json.dumps(result.model_dump()),
    )
    db.add(review)
    db.commit()
    return result.model_dump()


@router.post("/artifacts/{artifact_id}/review")
def review_artifact(artifact_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    version = _get_latest_version(db, artifact_id)
    content, filename = _read_artifact_content(db, artifact_id)

    result = review_code(content, filename)
    review = ArtifactReview(
        artifact_version_id=version.id,
        review_type="code_review",
        summary=result.summary,
        findings=json.dumps(result.model_dump()),
    )
    db.add(review)
    db.commit()
    return result.model_dump()


@router.get("/code-reviews/{review_id}")
def get_review(review_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    review = db.query(ArtifactReview).filter(ArtifactReview.id == review_id).first()
    if not review:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Review not found")
    return {"id": review.id, "summary": review.summary, "findings": review.findings}
