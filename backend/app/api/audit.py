import csv
import hashlib
import hmac
import io
import json
import logging
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

logger = logging.getLogger(__name__)
_NON_PG_WARNED = False  # one-shot warning when running on non-Postgres backends


def _strip_control_chars(value: str | None) -> str | None:
    """SC-031: drop CR / LF / NUL from any string written to an AuditLog
    column. A project member submitting ``notes="\\n2025-01-01 ADMIN
    admin_login\\n"`` could otherwise forge fake timeline rows in the CSV /
    PDF export. We strip the injection characters at write time so the stored
    value can never carry a line break or NUL into a downstream renderer.
    Other characters round-trip unchanged.
    """
    if value is None:
        return None
    return value.replace("\r", "").replace("\n", "").replace("\x00", "")


def _compute_entry_hash(log: AuditLog, prev_hash: str | None) -> str:
    """HMAC-SHA256 over canonical entry fields chained to previous hash.

    Uses AUDIT_HMAC_KEY (independent from JWT_SECRET_KEY) so JWT rotation does
    not invalidate historical chain verification.

    SC-012: ``impersonator_id`` is included in the canonical payload so
    impersonation attribution is HMAC-protected. Older rows written
    before the column existed hash with ``"impersonator": None``; the
    column defaults to NULL on existing rows so re-verification still
    matches.

    SC-031: ``event_metadata`` is now covered by the chain via
    ``sha256(event_metadata)``. Previously the HMAC excluded it, so an
    attacker could tamper with the (attacker-controlled) JSON blob without
    breaking the chain. Rows with no metadata hash ``"meta": None`` so
    historical re-verification still matches.
    """
    meta_digest = None
    if log.event_metadata is not None:
        meta_digest = hashlib.sha256(log.event_metadata.encode("utf-8")).hexdigest()
    payload = json.dumps({
        "id": log.id,
        "org": log.organization_id,
        "actor": log.actor_id,
        "impersonator": getattr(log, "impersonator_id", None),
        "action": log.action,
        "entity_type": log.entity_type,
        "entity_id": log.entity_id,
        "meta": meta_digest,
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
    impersonator_id: str | None = None,
):
    """Append an audit row chained off the org's last entry_hash.

    SC-012: when called from inside an impersonation session, pass
    ``impersonator_id`` so the row records both the target user (as
    ``actor_id``) and the super-admin who issued the impersonation
    token. Callers that don't pass it explicitly inherit it from
    ``request.state.impersonator_id`` which the auth middleware sets
    when the JWT carries an ``imp_by`` claim.

    Concurrency model:
      1. Acquire pg_advisory_xact_lock keyed by sha256(org_id) BEFORE
         the prev-row read. This serialises all chain writers for one
         org so reader-A and reader-B cannot both see row-N as the tip
         and both compute hash chained off N (which would silently
         break the chain).
      2. With the lock held, query the latest row + entry_hash. The
         ORDER BY uses (created_at DESC, id DESC) for a deterministic
         tie-break when two rows share a microsecond timestamp.
      3. Insert the new row + compute entry_hash + commit. The lock
         releases at COMMIT/ROLLBACK so the next writer can proceed.

    Non-Postgres backends (SQLite test runners) cannot use advisory
    locks; we emit a one-shot WARNING at startup of those test runs
    so the gap is visible rather than silent. Chain ordering still
    relies on the deterministic (created_at, id) sort to be correct
    for the single-writer test paths.
    """
    global _NON_PG_WARNED

    is_postgres = db.bind is not None and db.bind.dialect.name == "postgresql"
    if is_postgres:
        # Lock-then-read. The previous implementation read first then
        # locked, so two writers could observe the same prev tip.
        db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _org_lock_key(org_id)})
    else:
        if not _NON_PG_WARNED:
            logger.warning(
                "audit-chain: pg_advisory_xact_lock unavailable on dialect=%s; "
                "concurrent writers may race on prev_hash. SQLite paths are "
                "single-writer by design — Postgres is REQUIRED for prod.",
                db.bind.dialect.name if db.bind else "unknown",
            )
            _NON_PG_WARNED = True

    last = (
        db.query(AuditLog)
        .filter(AuditLog.organization_id == org_id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .first()
    )
    prev_hash = last.entry_hash if last else None

    # SC-012: fall back to request.state.impersonator_id when the caller
    # didn't pass it explicitly. The auth dependency sets that attribute
    # whenever the bearer's `imp_by` claim is present so every audit row
    # written during an impersonation session is automatically attributed.
    eff_impersonator = impersonator_id
    if eff_impersonator is None and request is not None:
        try:
            eff_impersonator = getattr(request.state, "impersonator_id", None)
        except Exception:
            eff_impersonator = None

    # SC-051: record the real client IP (rightmost-trusted X-Forwarded-For
    # entry when behind a configured proxy) instead of the proxy loopback.
    ip_address = None
    if request is not None:
        try:
            from app.utils.client_ip import get_client_ip
            ip_address = get_client_ip(request)
        except Exception:  # noqa: BLE001 — never block an audit write on this
            ip_address = request.client.host if request.client else None

    log = AuditLog(
        organization_id=org_id,
        actor_id=_strip_control_chars(actor_id),
        impersonator_id=_strip_control_chars(eff_impersonator),
        action=_strip_control_chars(action),
        entity_type=_strip_control_chars(entity_type),
        entity_id=_strip_control_chars(entity_id),
        # DB column `metadata` is NOT NULL (migration) though the model marks it
        # nullable; store an empty JSON object rather than NULL when no meta is
        # passed (e.g. first_admin_created) to satisfy the constraint.
        event_metadata=json.dumps(meta) if meta else "{}",
        ip_address=ip_address,
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
        .order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
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
