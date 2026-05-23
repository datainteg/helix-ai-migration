import hashlib
import hmac
import json
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.jwt import get_current_user_id
from app.auth.dependencies import require_permission
from app.models.observability import AuditLog, SystemHealthCheck
from app.core.config import settings

router = APIRouter(tags=["audit"])


def _compute_entry_hash(log: AuditLog, prev_hash: str | None) -> str:
    """HMAC-SHA256 over canonical entry fields chained to previous hash."""
    payload = json.dumps({
        "id": log.id,
        "org": log.organization_id,
        "actor": log.actor_id,
        "action": log.action,
        "entity_type": log.entity_type,
        "entity_id": log.entity_id,
        "prev": prev_hash or "GENESIS",
    }, sort_keys=True)
    return hmac.new(settings.JWT_SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()


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


@router.get("/audit-logs")
def list_audit_logs(
    user_id: str = Depends(require_permission("admin:audit:read")),
    db: Session = Depends(get_db),
):
    from app.services.auth_service import get_current_user
    user = get_current_user(db, user_id)
    org_id = user.memberships[0].organization_id
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.organization_id == org_id)
        .order_by(AuditLog.created_at.desc())
        .limit(50)
        .all()
    )
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


@router.get("/audit-logs/verify")
def verify_audit_chain(
    user_id: str = Depends(require_permission("admin:audit:read")),
    db: Session = Depends(get_db),
):
    """Walk the audit chain in chronological order and verify HMAC integrity."""
    from app.services.auth_service import get_current_user
    user = get_current_user(db, user_id)
    org_id = user.memberships[0].organization_id
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
