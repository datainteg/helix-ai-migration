"""Validation evidence + QA Agent review.

Helix generates validation test cases + expected evidence; the developer runs
the tests in their own environment and uploads RESULTS here (summaries, JSON,
screenshots, logs, notes). The QA agent reviews the uploaded evidence and
produces a review artifact. The VALIDATION lifecycle stage can only be approved
once at least one evidence item is accepted.

NO row-level production data is stored — evidence is test results/metadata only.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.evidence import ValidationEvidence
from app.services import lifecycle_constants as LC
from app.services import stage_lifecycle_service as sl
from app.services import artifact_review_service as ar

_VALID_TYPES = {"test_result", "screenshot", "log", "summary", "json"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_evidence(db: Session, org_id: str, evidence_id: str) -> ValidationEvidence:
    e = db.query(ValidationEvidence).filter(
        ValidationEvidence.id == evidence_id, ValidationEvidence.organization_id == org_id
    ).first()
    if not e:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return e


def _validation_stage_id(db: Session, org_id: str, project_id: str) -> str | None:
    try:
        st = sl._get_stage(db, org_id, project_id, LC.VALIDATION)
        return st.id
    except HTTPException:
        return None


# ── CRUD ─────────────────────────────────────────────────────────────
def create_evidence(db: Session, org_id: str, project_id: str, user_id: str, *,
                    evidence_type: str, title: str, description: str | None = None,
                    content_json: dict | None = None, file_path: str | None = None,
                    sprint_id: str | None = None) -> ValidationEvidence:
    sl._get_project(db, org_id, project_id)   # org-scope guard
    if evidence_type not in _VALID_TYPES:
        raise HTTPException(status_code=422, detail=f"evidence_type must be one of {sorted(_VALID_TYPES)}.")
    row = ValidationEvidence(
        organization_id=org_id, project_id=project_id, sprint_id=sprint_id,
        uploaded_by_user_id=user_id, evidence_type=evidence_type,
        title=title[:255], description=description, content_json=content_json,
        file_path=file_path, status="uploaded",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    sl._audit(db, org_id, user_id, "validation_evidence_uploaded", project_id, LC.VALIDATION, title[:120])
    return row


def list_evidence(db: Session, org_id: str, project_id: str) -> list[ValidationEvidence]:
    return (
        db.query(ValidationEvidence)
        .filter(ValidationEvidence.organization_id == org_id, ValidationEvidence.project_id == project_id)
        .order_by(ValidationEvidence.created_at.desc())
        .all()
    )


def get_evidence(db: Session, org_id: str, evidence_id: str) -> ValidationEvidence:
    return _get_evidence(db, org_id, evidence_id)


# ── QA Agent review ──────────────────────────────────────────────────
def qa_review_evidence(db: Session, org_id: str, evidence_id: str, user_id: str) -> dict:
    """Run the QA agent over an evidence item; store a validation-review
    artifact and link it to the evidence. Does not auto-accept — a human
    accepts/rejects after reading the review."""
    from agents.runtime.bmad_executor import execute_agent_skill

    ev = _get_evidence(db, org_id, evidence_id)
    ev.status = "under_review"
    db.commit()

    requirement = (
        f"# QA review of validation evidence\n"
        f"- Title: {ev.title}\n- Type: {ev.evidence_type}\n"
        f"- Developer notes: {ev.description or 'n/a'}\n"
        f"- Result JSON: {ev.content_json or 'n/a'}\n"
        f"- Uploaded file: {ev.file_path or 'none'}\n\n"
        "Review this validation evidence and produce a thorough Markdown report covering: "
        "test coverage, failed tests, missing evidence, data-quality risks, deployment readiness, "
        "and overall validation completeness. End with a clear recommendation (ACCEPT / REJECT / "
        "CHANGES REQUIRED) and a test-gap analysis."
    )
    result = execute_agent_skill(
        agent_code="bmad-agent-dev", skill_name="bmad-qa-generate-e2e-tests",
        project_id=ev.project_id, requirement_text=requirement,
        output_model=_qa_output_model(), upstream_agents=None,
        org_id=org_id, artifact_filename="validation-review", persist_file=False,
    )
    markdown = (result.artifact.body if result.artifact and result.artifact.body else result.raw_text) or ""
    artifact = ar.create_agent_artifact(
        db, org_id, ev.project_id, _validation_stage_id(db, org_id, ev.project_id),
        "validation-review", f"QA review — {ev.title}", markdown, None, "qa",
    )
    ev.reviewed_by_agent = "qa"
    ev.review_summary = (markdown[:1000] if markdown else None)
    ev.artifact_id = artifact.id   # link the evidence row to its QA-review artifact
    db.commit()
    db.refresh(ev)
    sl._audit(db, org_id, user_id, "validation_evidence_qa_reviewed", ev.project_id, LC.VALIDATION, ev.title[:120])
    return {"evidence_id": ev.id, "status": ev.status, "artifact_id": artifact.id, "mode": result.mode}


def _qa_output_model():
    # Local import keeps the permissive output contract in one place.
    from app.services.stage_agent_service import _StageArtifactMeta
    return _StageArtifactMeta


# ── Accept / reject ──────────────────────────────────────────────────
def accept_evidence(db: Session, org_id: str, evidence_id: str, user_id: str, comment: str | None = None) -> ValidationEvidence:
    ev = _get_evidence(db, org_id, evidence_id)
    ev.status = "accepted"
    ev.reviewed_by_user_id = user_id
    if comment:
        ev.review_summary = (ev.review_summary or "") + f"\n\n[accepted] {comment}"
    db.commit()
    db.refresh(ev)
    sl._audit(db, org_id, user_id, "validation_evidence_accepted", ev.project_id, LC.VALIDATION, ev.title[:120])
    return ev


def reject_evidence(db: Session, org_id: str, evidence_id: str, user_id: str, comment: str, changes_only: bool = False) -> ValidationEvidence:
    ev = _get_evidence(db, org_id, evidence_id)
    ev.status = "changes_required" if changes_only else "rejected"
    ev.reviewed_by_user_id = user_id
    ev.review_summary = (ev.review_summary or "") + f"\n\n[{ev.status}] {comment}"
    db.commit()
    db.refresh(ev)
    sl._audit(db, org_id, user_id, "validation_evidence_rejected", ev.project_id, LC.VALIDATION, comment[:120])
    return ev


def has_accepted_evidence(db: Session, org_id: str, project_id: str) -> bool:
    return db.query(ValidationEvidence).filter(
        ValidationEvidence.organization_id == org_id,
        ValidationEvidence.project_id == project_id,
        ValidationEvidence.status == "accepted",
    ).first() is not None
