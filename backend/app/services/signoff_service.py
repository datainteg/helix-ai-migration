"""Business sign-off workflow.

After the recon report is approved, a sign-off email DRAFT is created (never
auto-sent). The user reviews/edits recipients + subject + body, then sends it
via the org's configured email settings (SMTP/SendGrid — secrets stay in the
email-settings service). The recon report + validation summary are LINKED as
attachment references (the email body points to them; Helix does not exfiltrate
the files). Every sign-off event is audited; sent/approved/rejected status is
stored.
"""
from __future__ import annotations

import html
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.signoff import SignoffRequest
from app.models.project import Project, SourceConnection, TargetConnection
from app.models.evidence import ReconReport, ValidationEvidence
from app.services import lifecycle_constants as LC
from app.services import stage_lifecycle_service as sl


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get(db: Session, org_id: str, signoff_id: str) -> SignoffRequest:
    s = db.query(SignoffRequest).filter(SignoffRequest.id == signoff_id, SignoffRequest.organization_id == org_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Sign-off not found")
    return s


def _connectors(db: Session, org_id: str, project_id: str) -> tuple[str, str]:
    src = db.query(SourceConnection).filter(SourceConnection.project_id == project_id, SourceConnection.organization_id == org_id).first()
    tgt = db.query(TargetConnection).filter(TargetConnection.project_id == project_id, TargetConnection.organization_id == org_id).first()
    return (src.connector_type if src else "n/a"), (tgt.connector_type if tgt else "n/a")


def _approved_recon_or_409(db: Session, org_id: str, project_id: str, recon_report_id: str | None) -> ReconReport:
    """Resolve the recon report to sign off on — it MUST be approved. Sign-off
    cannot proceed on an unapproved or absent reconciliation report."""
    q = db.query(ReconReport).filter(ReconReport.organization_id == org_id, ReconReport.project_id == project_id)
    if recon_report_id:
        r = q.filter(ReconReport.id == recon_report_id).first()
        if not r:
            raise HTTPException(status_code=404, detail="Recon report not found")
        if r.status != "approved":
            raise HTTPException(status_code=409, detail="The reconciliation report must be approved before requesting sign-off.")
        return r
    r = q.filter(ReconReport.status == "approved").order_by(ReconReport.approved_at.desc().nullslast()).first()
    if not r:
        raise HTTPException(status_code=409, detail="Approve a reconciliation report before requesting sign-off.")
    return r


def _exec_summary(markdown: str | None) -> str:
    if not markdown:
        return "See the attached reconciliation report."
    # Take the text under the first "Executive summary" heading, else the head.
    lines = markdown.splitlines()
    out: list[str] = []
    capture = False
    for ln in lines:
        if ln.lower().startswith("#") and "executive" in ln.lower():
            capture = True; continue
        if capture and ln.startswith("#"):
            break
        if capture and ln.strip():
            out.append(ln.strip())
        if len(out) >= 6:
            break
    text = " ".join(out) if out else " ".join(l.strip() for l in lines[:6] if l.strip())
    return text[:800] or "See the attached reconciliation report."


def create_draft(db: Session, org_id: str, project_id: str, user_id: str, recon_report_id: str | None = None) -> SignoffRequest:
    project = sl._get_project(db, org_id, project_id)
    src, tgt = _connectors(db, org_id, project_id)
    recon = _approved_recon_or_409(db, org_id, project_id, recon_report_id)
    accepted = db.query(ValidationEvidence).filter(
        ValidationEvidence.organization_id == org_id, ValidationEvidence.project_id == project_id,
        ValidationEvidence.status == "accepted",
    ).count()
    alias = project.alias or project.name
    summary = _exec_summary(recon.report_markdown)
    has_pdf = bool(recon.report_pdf_path)
    report_ref = ("the attached reconciliation report" if has_pdf
                  else "the reconciliation report (available in Helix)")

    subject = f"Migration reconciliation sign-off required — {alias}"
    body = (
        f"<p>Dear reviewer,</p>"
        f"<p>The migration below has completed reconciliation and is ready for your business sign-off.</p>"
        f"<ul>"
        f"<li><b>Project:</b> {html.escape(project.name)} ({html.escape(alias)})</li>"
        f"<li><b>Source system:</b> {html.escape(src)}</li>"
        f"<li><b>Target system:</b> {html.escape(tgt)}</li>"
        f"<li><b>Validation:</b> {accepted} evidence item(s) accepted</li>"
        f"</ul>"
        f"<p><b>Reconciliation summary:</b><br/>{html.escape(summary)}</p>"
        f"<p><b>Approval requested:</b> please review {report_ref} and reply to "
        f"confirm sign-off, or request changes.</p>"
        f"<p><b>Next steps:</b> on your approval the project proceeds to documentation and closure.</p>"
        f"<p>Regards,<br/>Helix Migration</p>"
    )
    attachments: list[str] = []
    if recon.report_pdf_path:
        attachments.append(recon.report_pdf_path)
    attachments.append(f"validation-summary: {accepted} accepted evidence item(s)")

    row = SignoffRequest(
        organization_id=org_id, project_id=project_id,
        recon_report_id=recon.id,
        recipient_email=None, subject=subject, body=body,
        attachment_paths_json=attachments, status="draft", created_by_user_id=user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    sl._audit(db, org_id, user_id, "signoff_draft_created", project_id, LC.SIGN_OFF, f"recon={recon.id}")
    return row


def list_signoffs(db: Session, org_id: str, project_id: str) -> list[SignoffRequest]:
    return (
        db.query(SignoffRequest)
        .filter(SignoffRequest.organization_id == org_id, SignoffRequest.project_id == project_id)
        .order_by(SignoffRequest.created_at.desc())
        .all()
    )


def get_signoff(db: Session, org_id: str, signoff_id: str) -> SignoffRequest:
    return _get(db, org_id, signoff_id)


def update_draft(db: Session, org_id: str, signoff_id: str, user_id: str, *,
                 recipient_email: str | None = None, subject: str | None = None, body: str | None = None) -> SignoffRequest:
    s = _get(db, org_id, signoff_id)
    if s.status != "draft":
        raise HTTPException(status_code=409, detail=f"Sign-off is {s.status}; only a draft can be edited.")
    if recipient_email is not None:
        s.recipient_email = recipient_email[:255]
    if subject is not None:
        s.subject = subject[:500]
    if body is not None:
        s.body = body
    db.commit()
    db.refresh(s)
    return s


async def send_signoff(db: Session, org_id: str, signoff_id: str, user_id: str) -> SignoffRequest:
    s = _get(db, org_id, signoff_id)
    if s.status not in ("draft", "sent"):
        raise HTTPException(status_code=409, detail=f"Sign-off is {s.status}; cannot send.")
    if not s.recipient_email:
        raise HTTPException(status_code=409, detail="Set a recipient email before sending.")
    # Uses the org's configured email settings; never exposes SMTP secrets. If
    # email is disabled/unconfigured this logs and returns without raising — the
    # draft is still marked sent (the user explicitly chose to send).
    from app.services.email_service import send_email
    body_html = s.body or ""
    if s.attachment_paths_json:
        links = "".join(f"<li>{html.escape(str(p))}</li>" for p in s.attachment_paths_json)
        body_html += f"<hr/><p><b>Attached / referenced:</b></p><ul>{links}</ul>"
    await send_email(to=s.recipient_email, subject=s.subject or "Migration sign-off", html_body=body_html, db=db, organization_id=org_id)
    s.status = "sent"
    s.sent_at = _now()
    db.commit()
    db.refresh(s)
    sl._audit(db, org_id, user_id, "signoff_sent", s.project_id, LC.SIGN_OFF, s.recipient_email)
    return s


def mark_approved(db: Session, org_id: str, signoff_id: str, user_id: str, comment: str | None = None) -> SignoffRequest:
    s = _get(db, org_id, signoff_id)
    if s.status != "sent":
        raise HTTPException(status_code=409, detail=f"Sign-off is {s.status}; it must be sent before recording approval.")
    s.status = "approved"
    s.approved_at = _now()
    db.commit()
    db.refresh(s)
    sl._audit(db, org_id, user_id, "signoff_approved", s.project_id, LC.SIGN_OFF, comment)
    # Business approval completes the SIGN_OFF lifecycle stage and advances.
    try:
        sl.complete_stage(db, org_id, s.project_id, LC.SIGN_OFF, user_id, actor_type="user")
    except Exception:  # noqa: BLE001  (best-effort; the sign-off record is authoritative)
        db.rollback()
    return s


def mark_rejected(db: Session, org_id: str, signoff_id: str, user_id: str, comment: str | None = None) -> SignoffRequest:
    s = _get(db, org_id, signoff_id)
    if s.status != "sent":
        raise HTTPException(status_code=409, detail=f"Sign-off is {s.status}; it must be sent before recording a decision.")
    s.status = "rejected"
    s.approved_at = None
    db.commit()
    db.refresh(s)
    sl._audit(db, org_id, user_id, "signoff_rejected", s.project_id, LC.SIGN_OFF, comment)
    return s
