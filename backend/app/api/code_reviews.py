"""Ad-hoc code review endpoints — BMAD-native.

Each endpoint loads a single artifact from storage and invokes Amelia
(bmad-agent-dev) with the appropriate BMAD task skill:

  /artifacts/{id}/analyze → bmad-investigate  (forensic walkthrough)
  /artifacts/{id}/review  → bmad-code-review (adversarial review)

Both run through the HelixBMAD class facade so all the BMAD plumbing
(persona loading, persistent_facts, artifact handoff, LLM transport
selection) is shared with the migration pipeline.
"""

from __future__ import annotations

import json
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agents import HelixBMAD
from app.api.audit import write_audit
from app.auth.jwt import get_current_user_id
from app.auth.dependencies import resolve_active_org_id
from app.db.session import get_db
from app.models.artifacts import ArtifactReview, CodeArtifact, CodeArtifactVersion
from app.services.auth_service import get_current_user

router = APIRouter(tags=["code-reviews"])


class CodeReviewSummary(BaseModel):
    """Response shape for `GET /code-reviews/{review_id}`.

    `findings` is the raw string the BMAD agent emitted (typically a
    JSON-serialised object). Consumers should `JSON.parse(findings)` to
    get structured findings — documented here so the SDK contract is clear.
    """

    id: str
    summary: str | None = None
    findings: str | None = None


def _read_artifact_content(db: Session, org_id: str, artifact_id: str) -> tuple[str, str]:
    """Read actual artifact content from storage. Returns (content, filename)."""
    artifact = (
        db.query(CodeArtifact)
        .filter(CodeArtifact.id == artifact_id, CodeArtifact.organization_id == org_id)
        .first()
    )
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    path = artifact.storage_path
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Artifact file not found on storage")

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    return content, artifact.filename


def _get_latest_version(db: Session, org_id: str, artifact_id: str) -> CodeArtifactVersion:
    version = (
        db.query(CodeArtifactVersion)
        .join(CodeArtifact, CodeArtifactVersion.artifact_id == CodeArtifact.id)
        .filter(
            CodeArtifactVersion.artifact_id == artifact_id,
            CodeArtifact.organization_id == org_id,
        )
        .order_by(CodeArtifactVersion.version_number.desc())
        .first()
    )
    if not version:
        raise HTTPException(status_code=404, detail="No versions found")
    return version


def _resolve_org_id(db: Session, user_id: str) -> str:
    """Return the caller's active organization ID. Delegates to the shared
    resolver so suspended memberships are rejected consistently."""
    return resolve_active_org_id(db, user_id)


def _run_bmad_review(
    *,
    db: Session,
    request: Request,
    user_id: str,
    artifact_id: str,
    intent: str,
    review_type: str,
    audit_action: str,
) -> dict:
    org_id = _resolve_org_id(db, user_id)
    version = _get_latest_version(db, org_id, artifact_id)
    content, filename = _read_artifact_content(db, org_id, artifact_id)

    helix = HelixBMAD(
        project_id=f"adhoc-{artifact_id}",
        requirement_id=f"artifact-{artifact_id}",
        requirement_text=filename,
        organization_id=org_id,
    )
    result = helix.review_artifact(source_code=content, filename=filename, intent=intent)

    parsed = result.outputs.get(intent, {})
    review = ArtifactReview(
        artifact_version_id=version.id,
        review_type=review_type,
        summary=parsed.get("summary", ""),
        findings=json.dumps(parsed),
    )
    db.add(review)
    db.commit()

    write_audit(
        db,
        org_id=org_id,
        actor_id=user_id,
        action=audit_action,
        entity_type="artifact",
        entity_id=artifact_id,
        request=request,
    )
    return {
        **parsed,
        "artifact_paths": result.artifact_paths,
        "status": result.status,
    }


@router.post("/artifacts/{artifact_id}/analyze")
def analyze_artifact(
    request: Request,
    artifact_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Amelia (bmad-agent-dev) invokes bmad-investigate on the uploaded artifact."""
    return _run_bmad_review(
        db=db,
        request=request,
        user_id=user_id,
        artifact_id=artifact_id,
        intent="analyze",
        review_type="analysis",
        audit_action="artifact_analyzed",
    )


@router.post("/artifacts/{artifact_id}/review")
def review_artifact(
    request: Request,
    artifact_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Amelia (bmad-agent-dev) invokes bmad-code-review on the uploaded artifact."""
    return _run_bmad_review(
        db=db,
        request=request,
        user_id=user_id,
        artifact_id=artifact_id,
        intent="review",
        review_type="code_review",
        audit_action="artifact_reviewed",
    )


@router.get("/code-reviews/{review_id}", response_model=CodeReviewSummary)
def get_review(review_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    org_id = _resolve_org_id(db, user_id)
    review = (
        db.query(ArtifactReview)
        .join(CodeArtifactVersion, ArtifactReview.artifact_version_id == CodeArtifactVersion.id)
        .join(CodeArtifact, CodeArtifactVersion.artifact_id == CodeArtifact.id)
        .filter(ArtifactReview.id == review_id, CodeArtifact.organization_id == org_id)
        .first()
    )
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return CodeReviewSummary(id=review.id, summary=review.summary, findings=review.findings)
