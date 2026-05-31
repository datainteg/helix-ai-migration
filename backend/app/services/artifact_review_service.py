"""Markdown-artifact review lifecycle (migration_artifacts).

Agent creates v1 → user edit creates v2 → resubmit creates v3 → approval locks
the approved version. All versions remain readable; nothing is overwritten.
Org/project-scoped throughout.
"""
from __future__ import annotations

import difflib
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.migration_artifact import (
    MigrationArtifact, MigrationArtifactVersion,
    MigrationArtifactReview, MigrationArtifactComment,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_artifact(db: Session, org_id: str, artifact_id: str) -> MigrationArtifact:
    a = db.query(MigrationArtifact).filter(
        MigrationArtifact.id == artifact_id, MigrationArtifact.organization_id == org_id
    ).first()
    if not a:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return a


def _next_version_number(db: Session, artifact_id: str) -> int:
    vers = db.query(MigrationArtifactVersion.version_number).filter(
        MigrationArtifactVersion.artifact_id == artifact_id
    ).all()
    nums = [v[0] for v in vers if isinstance(v[0], int)]
    return (max(nums) + 1) if nums else 1


# ── Create / version ─────────────────────────────────────────────────
def create_agent_artifact(db: Session, org_id: str, project_id: str, stage_id: str | None,
                          artifact_type: str, title: str, content_markdown: str | None,
                          content_json: dict | None, agent_name: str) -> MigrationArtifact:
    """Agent output → new MigrationArtifact + v1, status=generated."""
    artifact = MigrationArtifact(
        organization_id=org_id, project_id=project_id, stage_id=stage_id,
        artifact_type=artifact_type, title=title, status="generated",
        created_by_agent=agent_name,
    )
    db.add(artifact)
    db.flush()
    v1 = MigrationArtifactVersion(
        artifact_id=artifact.id, version_number=1,
        content_markdown=content_markdown, content_json=content_json,
        change_summary="Initial agent generation",
        created_by_type="agent", created_by_agent=agent_name,
    )
    db.add(v1)
    db.flush()
    artifact.current_version_id = v1.id
    db.commit()
    db.refresh(artifact)
    return artifact


def create_artifact_version(db: Session, org_id: str, artifact_id: str, content_markdown: str | None,
                            content_json: dict | None, created_by_type: str, created_by_agent: str | None,
                            created_by_user_id: str | None, change_summary: str | None,
                            source_version_id: str | None = None) -> MigrationArtifactVersion:
    artifact = _get_artifact(db, org_id, artifact_id)
    if artifact.status == "approved":
        # Approved history is locked; a new edit re-opens the artifact as a new
        # version but the approved version row is never mutated.
        artifact.status = "resubmitted"
        artifact.approved_by_user_id = None
        artifact.approved_at = None
    version = MigrationArtifactVersion(
        artifact_id=artifact_id, version_number=_next_version_number(db, artifact_id),
        content_markdown=content_markdown, content_json=content_json,
        change_summary=change_summary, created_by_type=created_by_type,
        created_by_agent=created_by_agent, created_by_user_id=created_by_user_id,
        source_version_id=source_version_id,
    )
    db.add(version)
    db.flush()
    artifact.current_version_id = version.id
    db.commit()
    db.refresh(version)
    return version


def edit_artifact_version(db: Session, org_id: str, artifact_id: str, base_version_id: str | None,
                          new_content_markdown: str, user_id: str, change_summary: str | None) -> MigrationArtifactVersion:
    """User edit → new version (does NOT overwrite). Marks artifact changes_requested→resubmitted-ready."""
    v = create_artifact_version(
        db, org_id, artifact_id, new_content_markdown, None, "user", None, user_id,
        change_summary or "User edit", source_version_id=base_version_id,
    )
    artifact = _get_artifact(db, org_id, artifact_id)
    if artifact.status in ("changes_requested", "rejected", "under_review", "generated"):
        artifact.status = "resubmitted"
        db.commit()
    return v


def get_artifact(db: Session, org_id: str, artifact_id: str) -> MigrationArtifact:
    return _get_artifact(db, org_id, artifact_id)


def get_artifact_versions(db: Session, org_id: str, artifact_id: str) -> list[MigrationArtifactVersion]:
    _get_artifact(db, org_id, artifact_id)
    return (
        db.query(MigrationArtifactVersion)
        .filter(MigrationArtifactVersion.artifact_id == artifact_id)
        .order_by(MigrationArtifactVersion.version_number.desc())
        .all()
    )


def list_project_artifacts(db: Session, org_id: str, project_id: str) -> list[MigrationArtifact]:
    return (
        db.query(MigrationArtifact)
        .filter(MigrationArtifact.organization_id == org_id, MigrationArtifact.project_id == project_id)
        .order_by(MigrationArtifact.created_at.desc())
        .all()
    )


# ── Review transitions (each writes a review row) ─────────────────────
def _record_review(db: Session, artifact: MigrationArtifact, version_id: str, reviewer_user_id: str, status: str, comment: str | None) -> None:
    db.add(MigrationArtifactReview(
        organization_id=artifact.organization_id, project_id=artifact.project_id,
        artifact_id=artifact.id, artifact_version_id=version_id,
        reviewer_user_id=reviewer_user_id, status=status, comments=comment,
    ))


def submit_artifact_for_review(db: Session, org_id: str, artifact_id: str, version_id: str | None, user_id: str) -> MigrationArtifact:
    artifact = _get_artifact(db, org_id, artifact_id)
    vid = version_id or artifact.current_version_id
    if not vid:
        raise HTTPException(status_code=409, detail="Artifact has no version to submit.")
    artifact.status = "under_review"
    db.commit()
    return artifact


def approve_artifact(db: Session, org_id: str, artifact_id: str, version_id: str | None, reviewer_user_id: str, comment: str | None) -> MigrationArtifact:
    artifact = _get_artifact(db, org_id, artifact_id)
    vid = version_id or artifact.current_version_id
    if not vid:
        raise HTTPException(status_code=409, detail="Cannot approve: no current artifact version.")
    if artifact.status not in ("generated", "under_review", "resubmitted"):
        raise HTTPException(status_code=409, detail=f"Artifact is {artifact.status}; only generated/under_review/resubmitted can be approved.")
    artifact.status = "approved"
    artifact.current_version_id = vid          # lock the approved version
    artifact.approved_by_user_id = reviewer_user_id
    artifact.approved_at = _now()
    _record_review(db, artifact, vid, reviewer_user_id, "approved", comment)
    db.commit()
    return artifact


def reject_artifact(db: Session, org_id: str, artifact_id: str, version_id: str | None, reviewer_user_id: str, comment: str) -> MigrationArtifact:
    artifact = _get_artifact(db, org_id, artifact_id)
    vid = version_id or artifact.current_version_id
    artifact.status = "rejected"
    _record_review(db, artifact, vid, reviewer_user_id, "rejected", comment)
    db.commit()
    return artifact


def request_artifact_changes(db: Session, org_id: str, artifact_id: str, version_id: str | None, reviewer_user_id: str, comment: str) -> MigrationArtifact:
    artifact = _get_artifact(db, org_id, artifact_id)
    vid = version_id or artifact.current_version_id
    artifact.status = "changes_requested"
    _record_review(db, artifact, vid, reviewer_user_id, "changes_requested", comment)
    db.commit()
    return artifact


def add_artifact_comment(db: Session, org_id: str, artifact_id: str, version_id: str | None, user_id: str, comment: str) -> MigrationArtifactComment:
    artifact = _get_artifact(db, org_id, artifact_id)
    row = MigrationArtifactComment(
        organization_id=org_id, project_id=artifact.project_id, artifact_id=artifact_id,
        artifact_version_id=version_id, user_id=user_id, comment=comment,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_artifact_comments(db: Session, org_id: str, artifact_id: str) -> list[MigrationArtifactComment]:
    _get_artifact(db, org_id, artifact_id)
    return (
        db.query(MigrationArtifactComment)
        .filter(MigrationArtifactComment.artifact_id == artifact_id)
        .order_by(MigrationArtifactComment.created_at)
        .all()
    )


def compare_artifact_versions(db: Session, org_id: str, artifact_id: str, from_version: int, to_version: int) -> dict:
    _get_artifact(db, org_id, artifact_id)
    def _content(n: int) -> str:
        v = db.query(MigrationArtifactVersion).filter(
            MigrationArtifactVersion.artifact_id == artifact_id,
            MigrationArtifactVersion.version_number == n,
        ).first()
        if not v:
            raise HTTPException(status_code=404, detail=f"Version {n} not found")
        return v.content_markdown or ""
    a, b = _content(from_version), _content(to_version)
    diff = list(difflib.unified_diff(a.splitlines(), b.splitlines(),
                                     fromfile=f"v{from_version}", tofile=f"v{to_version}", lineterm=""))
    added = sum(1 for d in diff if d.startswith("+") and not d.startswith("+++"))
    removed = sum(1 for d in diff if d.startswith("-") and not d.startswith("---"))
    return {
        "artifact_id": artifact_id, "from_version": from_version, "to_version": to_version,
        "from_content": a, "to_content": b, "diff": "\n".join(diff),
        "added_lines": added, "removed_lines": removed,
    }
