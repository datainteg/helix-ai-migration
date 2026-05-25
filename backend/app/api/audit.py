import csv
import hashlib
import hmac
import io
import json
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.jwt import get_current_user_id
from app.auth.dependencies import require_permission
from app.models.observability import AuditLog, SystemHealthCheck
from app.core.config import settings

router = APIRouter(tags=["audit"])


def _compute_entry_hash(log: AuditLog, prev_hash: str | None) -> str:
    """HMAC-SHA256 over canonical entry fields chained to previous hash.

    Uses AUDIT_HMAC_KEY (independent from JWT_SECRET_KEY) so JWT rotation does
    not invalidate historical chain verification.
    """
    payload = json.dumps({
        "id": log.id,
        "org": log.organization_id,
        "actor": log.actor_id,
        "action": log.action,
        "entity_type": log.entity_type,
        "entity_id": log.entity_id,
        "prev": prev_hash or "GENESIS",
    }, sort_keys=True)
    return hmac.new(settings.AUDIT_HMAC_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()


def _org_lock_key(org_id: str) -> int:
    """Stable 63-bit signed int from org_id for pg_advisory_xact_lock."""
    digest = hashlib.sha256(org_id.encode()).digest()
    return int.from_bytes(digest[:8], "big", signed=False) & 0x7FFFFFFFFFFFFFFF


def write_audit(
    db: Session,
    org_id: str,
    actor_id: str,
    action: str,
    entity_type: str = "",
    entity_id: str = "",
    meta: dict = None,
    request: Request = None,
):
    # Serialize chain writes per-org so concurrent writers cannot race on
    # prev_hash lookup. Released at transaction end. Postgres-only; on other
    # backends the call is a no-op via try/except.
    try:
        db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _org_lock_key(org_id)})
    except Exception:
        pass

    last = (
        db.query(AuditLog)
        .filter(AuditLog.organization_id == org_id)
        .order_by(AuditLog.created_at.desc())
        .first()
    )
    prev_hash = last.entry_hash if last else None

    log = AuditLog(
        organization_id=org_id,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        event_metadata=json.dumps(meta) if meta else None,
        ip_address=request.client.host if request and request.client else None,
    )
    db.add(log)
    db.flush()
    log.entry_hash = _compute_entry_hash(log, prev_hash)
    db.commit()


def _get_org_logs(db: Session, user_id: str, limit: int = 500) -> tuple[str, list[AuditLog]]:
    from app.auth.dependencies import resolve_active_org_id
    org_id = resolve_active_org_id(db, user_id)
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.organization_id == org_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return org_id, logs


@router.get("/audit-logs")
def list_audit_logs(
    user_id: str = Depends(require_permission("admin:audit:read")),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=500),
):
    _, logs = _get_org_logs(db, user_id, limit=limit)
    return [
        {
            "id": l.id,
            "action": l.action,
            "entity_type": l.entity_type,
            "entity_id": l.entity_id,
            "actor_id": l.actor_id,
            "ip_address": l.ip_address,
            "entry_hash": l.entry_hash,
            "created_at": str(l.created_at),
        }
        for l in logs
    ]


@router.get("/audit-logs/export/csv")
def export_audit_csv(
    user_id: str = Depends(require_permission("admin:audit:read")),
    db: Session = Depends(get_db),
):
    """Export audit logs as CSV download."""
    _, logs = _get_org_logs(db, user_id, limit=500)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "action", "entity_type", "entity_id", "actor_id", "ip_address", "entry_hash", "created_at"])
    for l in logs:
        writer.writerow([l.id, l.action, l.entity_type, l.entity_id, l.actor_id, l.ip_address, l.entry_hash, l.created_at])

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit-logs.csv"},
    )


@router.get("/audit-logs/export/pdf")
def export_audit_pdf(
    user_id: str = Depends(require_permission("admin:audit:read")),
    db: Session = Depends(get_db),
):
    """Export audit logs as PDF download."""
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
    except ImportError:
        from fastapi import HTTPException
        raise HTTPException(status_code=501, detail="reportlab not installed — PDF export unavailable")

    _, logs = _get_org_logs(db, user_id, limit=200)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=30, bottomMargin=20)
    styles = getSampleStyleSheet()

    elements = [
        Paragraph(f"{settings.APP_NAME} — Audit Log", styles["Title"]),
        Spacer(1, 12),
    ]

    data = [["Timestamp", "Action", "Entity Type", "Entity ID", "Actor ID", "IP"]]
    for l in logs:
        data.append([
            str(l.created_at)[:19],
            l.action or "",
            l.entity_type or "",
            (l.entity_id or "")[:20],
            (l.actor_id or "")[:20],
            l.ip_address or "",
        ])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1d4ed8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4ff")]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e5e7eb")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(table)
    doc.build(elements)

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=audit-logs.pdf"},
    )


@router.get("/audit-logs/verify")
def verify_audit_chain(
    user_id: str = Depends(require_permission("admin:audit:read")),
    db: Session = Depends(get_db),
):
    """Walk the audit chain in chronological order and verify HMAC integrity."""
    from app.auth.dependencies import resolve_active_org_id
    org_id = resolve_active_org_id(db, user_id)
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.organization_id == org_id)
        .order_by(AuditLog.created_at.asc())
        .all()
    )
    broken: list[str] = []
    prev_hash: str | None = None
    for log in logs:
        expected = _compute_entry_hash(log, prev_hash)
        if log.entry_hash != expected:
            broken.append(log.id)
        prev_hash = log.entry_hash

    return {
        "total": len(logs),
        "valid": len(logs) - len(broken),
        "broken": broken,
        "integrity": "ok" if not broken else "tampered",
    }
