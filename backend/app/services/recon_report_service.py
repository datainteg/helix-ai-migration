"""Business-ready recon report (markdown + PDF) lifecycle.

The recon agent produces a business report; we persist it as a ReconReport row
(report_markdown) and render a PDF via reportlab. Reports are reviewed/approved
like other artifacts. No row-level production data is stored — the report holds
executive summaries, scope, check results and a sign-off recommendation only.
"""
from __future__ import annotations

import html
import os
import re
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.evidence import ReconReport
from app.services import lifecycle_constants as LC
from app.services import stage_lifecycle_service as sl
from app.services import recon_agent_service as ragent

_REPORT_DIR = os.getenv("HELIX_REPORT_DIR", "/app/recon-reports")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_report(db: Session, org_id: str, report_id: str) -> ReconReport:
    r = db.query(ReconReport).filter(ReconReport.id == report_id, ReconReport.organization_id == org_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Recon report not found")
    return r


# ── PDF rendering (reportlab) ────────────────────────────────────────
def _render_pdf(markdown: str, path: str, title: str) -> bool:
    """Render a simple, readable PDF from the report markdown. Best-effort —
    returns False if reportlab is unavailable / the path is not writable."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    except Exception:  # noqa: BLE001
        return False

    def _esc(s: str) -> str:
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"`(.+?)`", r"\1", s)
        # Escape stray XML chars but keep the <b> tags we just added.
        s = html.escape(s).replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
        return s

    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        styles = getSampleStyleSheet()
        doc = SimpleDocTemplate(path, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm,
                                leftMargin=18 * mm, rightMargin=18 * mm, title=title)
        flow = [Paragraph(_esc(title), styles["Title"]), Spacer(1, 6 * mm)]
        for raw in (markdown or "").splitlines():
            line = raw.rstrip()
            if not line.strip():
                flow.append(Spacer(1, 2.5 * mm)); continue
            if line.startswith("### "):
                flow.append(Paragraph(_esc(line[4:]), styles["Heading3"]))
            elif line.startswith("## "):
                flow.append(Paragraph(_esc(line[3:]), styles["Heading2"]))
            elif line.startswith("# "):
                flow.append(Paragraph(_esc(line[2:]), styles["Heading1"]))
            elif re.match(r"^\s*[-*]\s+", line):
                flow.append(Paragraph("• " + _esc(re.sub(r"^\s*[-*]\s+", "", line)), styles["BodyText"]))
            else:
                flow.append(Paragraph(_esc(line), styles["BodyText"]))
        doc.build(flow)
        return True
    except Exception:  # noqa: BLE001
        return False


# ── Report lifecycle ─────────────────────────────────────────────────
def generate_report(db: Session, org_id: str, project_id: str, user_id: str) -> ReconReport:
    project = sl._get_project(db, org_id, project_id)
    focus = (
        "Produce a BUSINESS-READY reconciliation report in Markdown with these sections: "
        "Executive summary; Source/target scope; Checks performed; Row count summary; "
        "Schema differences; Mismatch summary; Business rule results; Accepted exceptions; "
        "Risk summary; Sign-off recommendation. Be clear for a business audience while remaining "
        "technically precise. Do not include any row-level production data."
    )
    md, mode = ragent._run_recon_agent(db, org_id, project_id, focus)
    report = ReconReport(
        organization_id=org_id, project_id=project_id, report_type="business",
        status="generated", report_markdown=md, generated_by_agent="recon",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    # Render PDF (best-effort).
    path = os.path.join(_REPORT_DIR, project_id, f"recon-report-{report.id}.pdf")
    title = f"Reconciliation report — {project.alias or project.name}"
    if _render_pdf(md, path, title):
        report.report_pdf_path = path
        db.commit()
        db.refresh(report)
    sl._audit(db, org_id, user_id, "recon_report_generated", project_id, LC.RECONCILIATION, f"mode={mode} pdf={bool(report.report_pdf_path)}")
    return report


def list_reports(db: Session, org_id: str, project_id: str) -> list[ReconReport]:
    return (
        db.query(ReconReport)
        .filter(ReconReport.organization_id == org_id, ReconReport.project_id == project_id)
        .order_by(ReconReport.created_at.desc())
        .all()
    )


def get_report(db: Session, org_id: str, report_id: str) -> ReconReport:
    return _get_report(db, org_id, report_id)


def approve_report(db: Session, org_id: str, report_id: str, user_id: str, comment: str | None = None) -> ReconReport:
    r = _get_report(db, org_id, report_id)
    if r.status not in ("generated", "under_review", "changes_requested"):
        raise HTTPException(status_code=409, detail=f"Report is {r.status}; only generated/under_review/changes_requested can be approved.")
    r.status = "approved"
    r.approved_by_user_id = user_id
    r.approved_at = _now()
    db.commit()
    db.refresh(r)
    sl._audit(db, org_id, user_id, "recon_report_approved", r.project_id, LC.RECONCILIATION, comment)
    return r


def request_changes_report(db: Session, org_id: str, report_id: str, user_id: str, comment: str) -> ReconReport:
    r = _get_report(db, org_id, report_id)
    r.status = "changes_requested"
    db.commit()
    db.refresh(r)
    sl._audit(db, org_id, user_id, "recon_report_changes_requested", r.project_id, LC.RECONCILIATION, comment)
    return r


def get_report_pdf_path(db: Session, org_id: str, report_id: str) -> tuple[ReconReport, str]:
    r = _get_report(db, org_id, report_id)
    if not r.report_pdf_path or not os.path.exists(r.report_pdf_path):
        # Regenerate the PDF from the stored markdown on demand.
        path = os.path.join(_REPORT_DIR, r.project_id, f"recon-report-{r.id}.pdf")
        if _render_pdf(r.report_markdown or "", path, f"Reconciliation report {r.id}"):
            r.report_pdf_path = path
            db.commit()
        else:
            raise HTTPException(status_code=409, detail="PDF rendering is unavailable on this deployment.")
    return r, r.report_pdf_path
