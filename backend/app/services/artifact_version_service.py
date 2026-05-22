import hashlib
from sqlalchemy.orm import Session

from app.models.artifacts import CodeArtifact, CodeArtifactVersion
from app.schemas.artifacts import ArtifactResponse, ArtifactVersionResponse


def hash_content(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def create_artifact_metadata(db: Session, org_id: str, project_id: str, filename: str, file_type: str, storage_path: str, content: bytes) -> ArtifactResponse:
    content_hash = hash_content(content)
    artifact = CodeArtifact(
        organization_id=org_id, project_id=project_id,
        filename=filename, file_type=file_type,
        storage_path=storage_path, content_hash=content_hash,
    )
    db.add(artifact)
    db.flush()

    v1 = CodeArtifactVersion(
        artifact_id=artifact.id, version_number="1",
        content_hash=content_hash, storage_path=storage_path,
        approval_status="draft",
    )
    db.add(v1)
    db.commit()
    db.refresh(artifact)
    return ArtifactResponse.model_validate(artifact)


def list_artifacts(db: Session, project_id: str) -> list[ArtifactResponse]:
    artifacts = db.query(CodeArtifact).filter(CodeArtifact.project_id == project_id).all()
    return [ArtifactResponse.model_validate(a) for a in artifacts]


def get_artifact(db: Session, artifact_id: str) -> ArtifactResponse:
    artifact = db.query(CodeArtifact).filter(CodeArtifact.id == artifact_id).first()
    if not artifact:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Artifact not found")
    return ArtifactResponse.model_validate(artifact)


def list_versions(db: Session, artifact_id: str) -> list[ArtifactVersionResponse]:
    versions = db.query(CodeArtifactVersion).filter(CodeArtifactVersion.artifact_id == artifact_id).order_by(CodeArtifactVersion.version_number.desc()).all()
    return [ArtifactVersionResponse.model_validate(v) for v in versions]
