import hashlib
from sqlalchemy.orm import Session

from app.models.artifacts import CodeArtifact, CodeArtifactVersion
from app.schemas.artifacts import ArtifactResponse, ArtifactVersionResponse


def hash_content(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _vnum(v) -> int:
    """Numeric value of a String version_number (so '10' > '9'). Non-numeric → 0."""
    s = str(getattr(v, "version_number", "") or "")
    return int(s) if s.isdigit() else 0


def _path_within_allowed_roots(storage_path: str) -> bool:
    """True if a local storage_path resolves under a known artifact root
    (artifact storage, BMAD planning/implementation). s3:// is always allowed.
    Prevents the read endpoint from serving arbitrary files via a bad path."""
    if storage_path.startswith("s3://"):
        return True
    import os
    roots: list[str] = []
    try:
        from app.storage.local import _storage_root
        roots.append(str(_storage_root()))
    except Exception:  # noqa: BLE001
        pass
    try:
        from agents.runtime.artifact_store import _planning_root, _implementation_root
        roots.append(str(_planning_root()))
        roots.append(str(_implementation_root()))
    except Exception:  # noqa: BLE001
        pass
    try:
        real = os.path.realpath(storage_path)
    except Exception:  # noqa: BLE001
        return False
    return any(r and (real == r or real.startswith(r.rstrip("/") + os.sep)) for r in roots)


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


def list_artifacts(db: Session, org_id: str, project_id: str) -> list[ArtifactResponse]:
    artifacts = db.query(CodeArtifact).filter(
        CodeArtifact.organization_id == org_id,
        CodeArtifact.project_id == project_id,
    ).all()
    return [ArtifactResponse.model_validate(a) for a in artifacts]


def get_artifact(db: Session, org_id: str, artifact_id: str) -> ArtifactResponse:
    artifact = db.query(CodeArtifact).filter(
        CodeArtifact.id == artifact_id,
        CodeArtifact.organization_id == org_id,
    ).first()
    if not artifact:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Artifact not found")
    return ArtifactResponse.model_validate(artifact)


_MAX_CONTENT_BYTES = 512 * 1024  # cap inline content payloads (code artifacts are text)


def read_artifact_content(db: Session, org_id: str, artifact_id: str, version_number: str | None = None) -> dict:
    """Return the decoded text content of an artifact version (org-scoped).

    version_number=None → the latest version (falls back to the artifact's own
    storage_path if no version rows exist). Reads real stored bytes via the
    storage driver; never fabricates content. Caps the payload and decodes as
    UTF-8 (replace) since artifacts are SQL/text. On a read failure returns
    content=None + a note rather than 500, so the UI can show an honest state.
    """
    from fastapi import HTTPException

    artifact = db.query(CodeArtifact).filter(
        CodeArtifact.id == artifact_id,
        CodeArtifact.organization_id == org_id,
    ).first()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    q = db.query(CodeArtifactVersion).filter(CodeArtifactVersion.artifact_id == artifact_id)
    if version_number is not None:
        version = q.filter(CodeArtifactVersion.version_number == version_number).first()
        if not version:
            raise HTTPException(status_code=404, detail="Artifact version not found")
    else:
        # version_number is a String; pick the latest NUMERICALLY (a DB desc()
        # sorts lexicographically → '9' > '10'). Sort in Python.
        version = max(q.all(), key=_vnum, default=None)

    storage_path = version.storage_path if version else artifact.storage_path
    resolved_version = version.version_number if version else "1"
    content_hash = version.content_hash if version else artifact.content_hash

    base = {
        "artifact_id": artifact_id,
        "version_number": resolved_version,
        "file_type": artifact.file_type,
        "filename": artifact.filename,
        "content_hash": content_hash,
    }
    if not storage_path:
        return {**base, "content": None, "truncated": False, "size_bytes": 0, "note": "No stored content path."}
    # Containment guard (defence-in-depth): only serve files under a known
    # storage root. The write path enforces this; the read path must too, so a
    # poisoned/buggy storage_path can't read arbitrary server files.
    if not _path_within_allowed_roots(storage_path):
        return {**base, "content": None, "truncated": False, "size_bytes": 0, "note": "Content path is outside the allowed storage roots."}
    try:
        from app.storage.s3 import read_artifact_bytes
        raw = read_artifact_bytes(storage_path)
    except Exception as exc:  # noqa: BLE001 — surface as honest empty state, not 500
        return {**base, "content": None, "truncated": False, "size_bytes": 0, "note": f"Content unavailable: {exc}"}
    truncated = len(raw) > _MAX_CONTENT_BYTES
    text = raw[:_MAX_CONTENT_BYTES].decode("utf-8", errors="replace")
    return {**base, "content": text, "truncated": truncated, "size_bytes": len(raw)}


def save_artifact_edit(
    db: Session, org_id: str, artifact_id: str, content: str,
    change_summary: str | None = None, editor_user_id: str | None = None,
) -> dict:
    """Save an edited artifact as a NEW version (history preserved).

    Writes the new bytes via the storage driver, inserts a CodeArtifactVersion
    with the next version number, and points the artifact's head
    storage_path/content_hash at it. Returns the new version's content payload
    (same shape as read_artifact_content). Used when a human corrects
    AI-generated output (extra/missing statements, etc.).
    """
    from fastapi import HTTPException

    artifact = db.query(CodeArtifact).filter(
        CodeArtifact.id == artifact_id,
        CodeArtifact.organization_id == org_id,
    ).first()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    raw = (content or "").encode("utf-8")
    new_hash = hash_content(raw)

    from app.storage.s3 import save_artifact
    storage_path = save_artifact(artifact.project_id, artifact.filename, raw)

    existing = db.query(CodeArtifactVersion).filter(CodeArtifactVersion.artifact_id == artifact_id).all()
    next_version = max((int(v.version_number) if str(v.version_number).isdigit() else 1) for v in existing) + 1 if existing else 1

    version = CodeArtifactVersion(
        artifact_id=artifact_id, version_number=str(next_version),
        content_hash=new_hash, storage_path=storage_path,
        change_summary=change_summary or "Manual edit",
        approval_status="draft", generated_by_agent="human",
        approved_by=editor_user_id,
    )
    db.add(version)
    # Point the artifact head at the new content.
    artifact.storage_path = storage_path
    artifact.content_hash = new_hash
    db.commit()

    return {
        "artifact_id": artifact_id,
        "version_number": str(next_version),
        "file_type": artifact.file_type,
        "filename": artifact.filename,
        "content_hash": new_hash,
        "content": content,
        "truncated": False,
        "size_bytes": len(raw),
    }


def list_versions(db: Session, org_id: str, artifact_id: str) -> list[ArtifactVersionResponse]:
    artifact = db.query(CodeArtifact).filter(
        CodeArtifact.id == artifact_id,
        CodeArtifact.organization_id == org_id,
    ).first()
    if not artifact:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Artifact not found")

    versions = (
        db.query(CodeArtifactVersion)
        .join(CodeArtifact, CodeArtifactVersion.artifact_id == CodeArtifact.id)
        .filter(CodeArtifactVersion.artifact_id == artifact_id, CodeArtifact.organization_id == org_id)
        .all()
    )
    # Newest first, NUMERICALLY (String column → DB sort is lexicographic).
    versions.sort(key=_vnum, reverse=True)
    return [ArtifactVersionResponse.model_validate(v) for v in versions]
