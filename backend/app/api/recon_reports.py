"""Recon Agent + business report API.

RBAC: plan/code/report generation needs project:write; approve/request-changes
needs agent:approve; reads + download need project:read. Recon code is DRAFT and
is never executed by Helix.
"""
import os

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.dependencies import get_current_organization_id, require_permission
from app.services.project_service import ensure_project_access
from app.services import recon_agent_service as ragent
from app.services import recon_report_service as rreport
from app.schemas.lifecycle import StageActionRequest, StageRejectRequest

router = APIRouter(tags=["recon-reports"])


def _report(r) -> dict:
    return {
        "id": r.id, "project_id": r.project_id, "sprint_id": r.sprint_id, "report_type": r.report_type,
        "status": r.status, "report_markdown": r.report_markdown,
        "has_pdf": bool(r.report_pdf_path), "generated_by_agent": r.generated_by_agent,
        "source_summary_json": r.source_summary_json, "target_summary_json": r.target_summary_json,
        "mismatch_summary_json": r.mismatch_summary_json, "business_rules_json": r.business_rules_json,
        "approved_by_user_id": r.approved_by_user_id,
        "approved_at": str(r.approved_at) if r.approved_at else None,
        "created_at": str(r.created_at) if r.created_at else None,
    }


def _code(c) -> dict:
    return {"id": c.id, "file_name": c.file_name, "file_type": c.file_type, "language": c.language,
            "status": c.status, "generated_by_agent": c.generated_by_agent}


# ── Generation ───────────────────────────────────────────────────────
@router.post("/projects/{project_id}/recon/generate-plan", status_code=201)
def generate_plan(project_id: str, org_id: str = Depends(get_current_organization_id),
                  user_id: str = Depends(require_permission("project:write")), db: Session = Depends(get_db)):
    ensure_project_access(db, org_id, project_id)
    a = ragent.generate_recon_plan(db, org_id, project_id, user_id)
    return {"artifact_id": a.id, "artifact_type": a.artifact_type, "status": a.status, "title": a.title}


@router.post("/projects/{project_id}/recon/generate-code", status_code=201)
def generate_code(project_id: str, org_id: str = Depends(get_current_organization_id),
                  user_id: str = Depends(require_permission("project:write")), db: Session = Depends(get_db)):
    ensure_project_access(db, org_id, project_id)
    rows = ragent.generate_recon_code(db, org_id, project_id, user_id)
    return {"created": len(rows), "files": [_code(r) for r in rows]}


@router.post("/projects/{project_id}/recon/generate-report", status_code=201)
def generate_report(project_id: str, org_id: str = Depends(get_current_organization_id),
                    user_id: str = Depends(require_permission("project:write")), db: Session = Depends(get_db)):
    ensure_project_access(db, org_id, project_id)
    return _report(rreport.generate_report(db, org_id, project_id, user_id))


# ── Reports ──────────────────────────────────────────────────────────
@router.get("/projects/{project_id}/recon/reports")
def list_reports(project_id: str, org_id: str = Depends(get_current_organization_id),
                 user_id: str = Depends(require_permission("project:read")), db: Session = Depends(get_db)):
    ensure_project_access(db, org_id, project_id)
    return [_report(r) for r in rreport.list_reports(db, org_id, project_id)]


@router.get("/recon/reports/{report_id}")
def get_report(report_id: str, org_id: str = Depends(get_current_organization_id),
               user_id: str = Depends(require_permission("project:read")), db: Session = Depends(get_db)):
    return _report(rreport.get_report(db, org_id, report_id))


@router.post("/recon/reports/{report_id}/approve")
def approve_report(report_id: str, data: StageActionRequest,
                   org_id: str = Depends(get_current_organization_id),
                   user_id: str = Depends(require_permission("agent:approve")), db: Session = Depends(get_db)):
    return _report(rreport.approve_report(db, org_id, report_id, user_id, data.comment))


@router.post("/recon/reports/{report_id}/request-changes")
def request_changes(report_id: str, data: StageRejectRequest,
                    org_id: str = Depends(get_current_organization_id),
                    user_id: str = Depends(require_permission("agent:approve")), db: Session = Depends(get_db)):
    return _report(rreport.request_changes_report(db, org_id, report_id, user_id, data.comment))


@router.get("/recon/reports/{report_id}/download")
def download_report(report_id: str, org_id: str = Depends(get_current_organization_id),
                    user_id: str = Depends(require_permission("project:read")), db: Session = Depends(get_db)):
    r, path = rreport.get_report_pdf_path(db, org_id, report_id)
    return FileResponse(path, media_type="application/pdf", filename=os.path.basename(path))
