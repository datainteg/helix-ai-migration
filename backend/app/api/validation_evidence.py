"""Validation evidence + QA review API.

Evidence upload accepts an optional file plus structured fields (markdown
summary as `description`, JSON result as `content_json`). Bytes are written to a
dedicated evidence directory (never executed); only test results/metadata are
stored — no row-level production data.

RBAC: upload/qa-review need project:write; accept/reject need agent:approve.
"""
import json
import os
import re
import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.dependencies import get_current_organization_id, require_permission
from app.services.project_service import ensure_project_access
from app.services import validation_evidence_service as svc
from app.schemas.lifecycle import StageRejectRequest

router = APIRouter(tags=["validation-evidence"])

_EVIDENCE_DIR = os.getenv("HELIX_EVIDENCE_DIR", "/app/evidence-uploads")
_MAX_BYTES = 25 * 1024 * 1024   # 25 MB cap


def _ev(e) -> dict:
    return {
        "id": e.id, "project_id": e.project_id, "sprint_id": e.sprint_id, "artifact_id": e.artifact_id,
        "uploaded_by_user_id": e.uploaded_by_user_id, "evidence_type": e.evidence_type,
        "title": e.title, "description": e.description, "file_path": e.file_path,
        "content_json": e.content_json, "status": e.status,
        "reviewed_by_agent": e.reviewed_by_agent, "reviewed_by_user_id": e.reviewed_by_user_id,
        "review_summary": e.review_summary,
        "created_at": str(e.created_at) if e.created_at else None,
    }


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name or "evidence")[:120] or "evidence"


def _save_file(project_id: str, upload: UploadFile) -> tuple[str | None, int]:
    """Persist the uploaded bytes to the evidence dir. Best-effort: on a
    read-only/unavailable path we keep metadata only (returns (None, size))."""
    data = upload.file.read(_MAX_BYTES + 1)
    size = len(data)
    if size > _MAX_BYTES:
        from fastapi import HTTPException
        raise HTTPException(status_code=413, detail="Evidence file exceeds 25 MB limit.")
    try:
        d = os.path.join(_EVIDENCE_DIR, project_id)
        os.makedirs(d, exist_ok=True)
        fname = f"{uuid.uuid4().hex}_{_safe_name(upload.filename or 'file')}"
        path = os.path.join(d, fname)
        with open(path, "wb") as fh:
            fh.write(data)
        return path, size
    except OSError:
        return None, size


@router.post("/projects/{project_id}/validation/evidence", status_code=201)
def upload_evidence(
    project_id: str,
    evidence_type: str = Form("summary"),
    title: str = Form(...),
    description: str | None = Form(None),
    content_json: str | None = Form(None),
    sprint_id: str | None = Form(None),
    file: UploadFile | None = File(None),
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(require_permission("project:write")),
    db: Session = Depends(get_db),
):
    ensure_project_access(db, org_id, project_id)
    parsed_json: dict | None = None
    if content_json:
        try:
            parsed_json = json.loads(content_json)
        except json.JSONDecodeError:
            parsed_json = {"raw": content_json}
    file_path = None
    if file is not None and file.filename:
        file_path, size = _save_file(project_id, file)
        parsed_json = {**(parsed_json or {}), "_file": {"name": file.filename, "size": size, "stored": bool(file_path)}}
    row = svc.create_evidence(
        db, org_id, project_id, user_id,
        evidence_type=evidence_type, title=title, description=description,
        content_json=parsed_json, file_path=file_path, sprint_id=sprint_id,
    )
    return _ev(row)


@router.get("/projects/{project_id}/validation/evidence")
def list_evidence(project_id: str, org_id: str = Depends(get_current_organization_id),
                  user_id: str = Depends(require_permission("project:read")), db: Session = Depends(get_db)):
    ensure_project_access(db, org_id, project_id)
    return [_ev(e) for e in svc.list_evidence(db, org_id, project_id)]


@router.get("/validation/evidence/{evidence_id}")
def get_evidence(evidence_id: str, org_id: str = Depends(get_current_organization_id),
                 user_id: str = Depends(require_permission("project:read")), db: Session = Depends(get_db)):
    return _ev(svc.get_evidence(db, org_id, evidence_id))


@router.post("/validation/evidence/{evidence_id}/qa-review")
def qa_review(evidence_id: str, org_id: str = Depends(get_current_organization_id),
              user_id: str = Depends(require_permission("project:write")), db: Session = Depends(get_db)):
    return svc.qa_review_evidence(db, org_id, evidence_id, user_id)


@router.post("/validation/evidence/{evidence_id}/accept")
def accept(evidence_id: str, org_id: str = Depends(get_current_organization_id),
           user_id: str = Depends(require_permission("agent:approve")), db: Session = Depends(get_db)):
    return _ev(svc.accept_evidence(db, org_id, evidence_id, user_id))


@router.post("/validation/evidence/{evidence_id}/reject")
def reject(evidence_id: str, data: StageRejectRequest, changes_only: bool = False,
           org_id: str = Depends(get_current_organization_id),
           user_id: str = Depends(require_permission("agent:approve")), db: Session = Depends(get_db)):
    """Reject evidence. `changes_only=true` marks it `changes_required` (fixable)
    rather than a hard `rejected`."""
    return _ev(svc.reject_evidence(db, org_id, evidence_id, user_id, data.comment, changes_only=changes_only))
