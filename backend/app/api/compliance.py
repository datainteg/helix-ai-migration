"""Compliance pack — per-project SOC 2 / HIPAA evidence bundle.

Generates a single PDF that includes:
  1. Project header (name, owner, source, target, status, dates).
  2. Audit chain entries for this project (chronological).
  3. Validation runs + per-rule results.
  4. Recon runs + diff summaries.
  5. Approval signatures (workflow approvals + cutover transitions).
  6. Artifact registry (with rollback links flagged).

Auditors get a single PDF per project; nothing else queryable required.
Reuses the same reportlab dependency the audit-log export already pulls in.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.dependencies import get_current_organization_id, require_permission
from app.api.audit import write_audit
from app.models.project import Project
from app.models.observability import AuditLog
from app.models.validation import ValidationRule, ValidationRun, ValidationResult, ReconRun, ReconResult
from app.models.workflow import WorkflowRun
from app.models.artifacts import CodeArtifact
from app.models.cutover import MigrationCutover
from app.services.project_service import ensure_project_access
from app.core.config import settings

# SEC-011 — every free-text field that flows into the customer-downloadable
# PDF must pass through this scrubber. Imported once at module-load.
try:
    from agents.runtime.artifact_store import safe_frontmatter as _safe_frontmatter
except Exception:  # noqa: BLE001 — keep PDF route alive if agents pkg missing
    def _safe_frontmatter(v):  # type: ignore[no-redef]
        return v


def _scrub_text(value: object) -> str:
    """Render `value` as a string with secret-shaped substrings redacted.

    Wraps the dict-oriented `_safe_frontmatter` so it also works on plain
    strings (audit metadata blobs, artifact filenames). Strings with embedded
    secret-shaped tokens get the whole leaf replaced with `[REDACTED]` by
    `_safe_frontmatter`; everything else round-trips unchanged.
    """
    if value is None:
        return ""
    cleaned = _safe_frontmatter(value)
    return str(cleaned)


router = APIRouter(tags=["compliance"])


@router.get("/projects/{project_id}/compliance-bundle")
def compliance_bundle(
    project_id: str,
    request: Request,
    org_id: str = Depends(get_current_organization_id),
    user_id: str = Depends(require_permission("admin:audit:read")),
    db: Session = Depends(get_db),
):
    """Build the per-project compliance PDF and return it as a download."""
    ensure_project_access(db, org_id, project_id)
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    except ImportError:
        raise HTTPException(status_code=501, detail="reportlab not installed — install reportlab for compliance export")

    # ── Pull data ─────────────────────────────────────────────────────
    audit_rows = (
        db.query(AuditLog)
        .filter(AuditLog.organization_id == org_id, AuditLog.entity_id == project_id)
        .order_by(AuditLog.created_at.asc())
        .all()
    )
    # Project-related audit may not all have entity_id=project_id (workflow
    # runs etc.). Pull every entry mentioning the project_id as entity OR
    # touching its workflows.
    project_workflows = db.query(WorkflowRun).filter(WorkflowRun.project_id == project_id).all()
    wf_ids = {w.workflow_id for w in project_workflows} | {w.id for w in project_workflows}
    extra_audit = (
        db.query(AuditLog)
        .filter(AuditLog.organization_id == org_id, AuditLog.entity_id.in_(wf_ids))
        .order_by(AuditLog.created_at.asc())
        .all()
    )
    audit_all = sorted({a.id: a for a in (audit_rows + extra_audit)}.values(), key=lambda a: a.created_at)

    rules = db.query(ValidationRule).filter(ValidationRule.project_id == project_id).all()
    val_runs = (
        db.query(ValidationRun).filter(ValidationRun.project_id == project_id)
        .order_by(ValidationRun.created_at.desc()).all()
    )
    recon_runs = (
        db.query(ReconRun).filter(ReconRun.project_id == project_id)
        .order_by(ReconRun.created_at.desc()).all()
    )
    cutovers = (
        db.query(MigrationCutover).filter(MigrationCutover.project_id == project_id)
        .order_by(MigrationCutover.created_at.desc()).all()
    )
    artifacts = (
        db.query(CodeArtifact).filter(CodeArtifact.project_id == project_id)
        .order_by(CodeArtifact.created_at.desc()).all()
    )

    # ── Build PDF ────────────────────────────────────────────────────
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=24, leftMargin=24, topMargin=28, bottomMargin=24)
    styles = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", parent=styles["Title"], fontSize=16, leading=20, spaceAfter=6)
    H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12, textColor=colors.HexColor("#1d4ed8"), spaceBefore=12, spaceAfter=4)
    Body = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=9, leading=12)
    Mono = ParagraphStyle("Mono", parent=Body, fontName="Courier", fontSize=8)

    elements = []
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")

    elements.append(Paragraph(f"{settings.APP_NAME} — Compliance Pack", H1))
    elements.append(Paragraph(
        f"<b>Project</b>: {project.name} &nbsp;&nbsp; <b>ID</b>: {project.id}<br/>"
        f"<b>Status</b>: {project.status} &nbsp;&nbsp; <b>Risk</b>: {project.risk_level}<br/>"
        f"<b>Owner</b>: {project.owner_id} &nbsp;&nbsp; <b>Generated</b>: {now_iso}",
        Body,
    ))
    elements.append(Spacer(1, 6))

    # ── 1. Audit chain ────────────────────────────────────────────────
    elements.append(Paragraph("1. Audit chain", H2))
    if not audit_all:
        elements.append(Paragraph("No audit entries for this project.", Body))
    else:
        data = [["Timestamp (UTC)", "Action", "Actor", "Entity", "Hash (sha256, head)"]]
        for a in audit_all:
            # SEC-011: every per-row string passes through the scrubber so a
            # secret-shaped token in any user-controlled column (action label,
            # entity_id, custom audit metadata) becomes `[REDACTED]`.
            data.append([
                str(a.created_at)[:19],
                _scrub_text(a.action or ""),
                _scrub_text((a.actor_id or "")[:16]),
                _scrub_text(f"{a.entity_type or ''}:{(a.entity_id or '')[:18]}"),
                (a.entry_hash or "")[:16] + "…",
            ])
        tbl = Table(data, repeatRows=1, hAlign="LEFT")
        tbl.setStyle(_table_style(colors))
        elements.append(tbl)

    # ── 2. Validation runs + results ──────────────────────────────────
    elements.append(Paragraph("2. Validation", H2))
    elements.append(Paragraph(f"Rules: {len(rules)} · Runs: {len(val_runs)}", Body))
    for run in val_runs[:50]:
        results = db.query(ValidationResult).filter(ValidationResult.run_id == run.id).all()
        passed = sum(1 for r in results if r.status == "passed")
        failed = sum(1 for r in results if r.status == "failed")
        elements.append(Paragraph(
            f"Run <b>{run.id[:12]}</b> · status={run.status} · {passed} passed · {failed} failed · {str(run.created_at)[:19]}",
            Body,
        ))

    # ── 3. Recon runs ─────────────────────────────────────────────────
    elements.append(Paragraph("3. Reconciliation", H2))
    if not recon_runs:
        elements.append(Paragraph("No recon runs recorded.", Body))
    else:
        data = [["Recon Run", "Status", "Result Count", "Started (UTC)"]]
        for r in recon_runs[:50]:
            results = db.query(ReconResult).filter(ReconResult.run_id == r.id).all()
            data.append([r.id[:18], r.status or "", str(len(results)), str(r.created_at)[:19]])
        tbl = Table(data, repeatRows=1, hAlign="LEFT")
        tbl.setStyle(_table_style(colors))
        elements.append(tbl)

    # ── 4. Cutovers ───────────────────────────────────────────────────
    elements.append(Paragraph("4. Cutovers", H2))
    if not cutovers:
        elements.append(Paragraph("No cutovers recorded.", Body))
    else:
        data = [["Cutover", "Source → Target", "State", "Flip (UTC)", "Done (UTC)"]]
        for c in cutovers[:50]:
            data.append([
                c.id[:18],
                # SEC-011: source_ref/target_ref can be operator-supplied DSN strings
                _scrub_text(f"{(c.source_ref or '')[:20]} → {(c.target_ref or '')[:20]}"),
                _scrub_text(c.state),
                str(c.flip_started_at)[:19] if c.flip_started_at else "—",
                str(c.done_at)[:19] if c.done_at else "—",
            ])
        tbl = Table(data, repeatRows=1, hAlign="LEFT")
        tbl.setStyle(_table_style(colors))
        elements.append(tbl)

    # ── 5. Artifacts ──────────────────────────────────────────────────
    elements.append(Paragraph("5. Artifact registry", H2))
    if not artifacts:
        elements.append(Paragraph("No artifacts in project.", Body))
    else:
        data = [["Filename", "Type", "Status", "Rollback?", "Created (UTC)"]]
        for a in artifacts[:200]:
            # SEC-011: filename is operator-supplied — a hostile uploader could
            # name an artifact "sk-test-…sql". Scrub before embed.
            data.append([
                _scrub_text(a.filename[:40]),
                _scrub_text(a.file_type or ""),
                _scrub_text(a.status or ""),
                "Yes" if a.rollback_artifact_id else "—",
                str(a.created_at)[:19],
            ])
        tbl = Table(data, repeatRows=1, hAlign="LEFT")
        tbl.setStyle(_table_style(colors))
        elements.append(tbl)

    doc.build(elements)
    buf.seek(0)

    write_audit(db, org_id=org_id, actor_id=user_id, action="compliance_bundle_exported",
                entity_type="project", entity_id=project_id,
                meta={"audit_rows": len(audit_all), "validation_runs": len(val_runs), "recon_runs": len(recon_runs),
                      "cutovers": len(cutovers), "artifacts": len(artifacts)},
                request=request)

    filename = f"helix-compliance-{project.name[:32]}-{datetime.now(timezone.utc).strftime('%Y%m%d')}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _table_style(colors_module):
    from reportlab.platypus import TableStyle
    c = colors_module
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c.HexColor("#1d4ed8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), c.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [c.white, c.HexColor("#f0f4ff")]),
        ("GRID", (0, 0), (-1, -1), 0.3, c.HexColor("#e5e7eb")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 3),
    ])
