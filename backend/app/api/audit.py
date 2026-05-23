import json
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.jwt import get_current_user_id
from app.auth.dependencies import require_permission
from app.models.observability import AuditLog, SystemHealthCheck
from app.core.config import settings

router = APIRouter(tags=["audit"])


def write_audit(db: Session, org_id: str, actor_id: str, action: str, entity_type: str = "", entity_id: str = "", meta: dict = None, request: Request = None):
    log = AuditLog(
        organization_id=org_id, actor_id=actor_id, action=action,
        entity_type=entity_type, entity_id=entity_id,
        event_metadata=json.dumps(meta) if meta else None,
        ip_address=request.client.host if request else None,
    )
    db.add(log)
    db.commit()


@router.get("/audit-logs")
def list_audit_logs(user_id: str = Depends(require_permission("admin:audit:read")), db: Session = Depends(get_db)):
    from app.services.auth_service import get_current_user
    user = get_current_user(db, user_id)
    org_id = user.memberships[0].organization_id
    logs = db.query(AuditLog).filter(AuditLog.organization_id == org_id).order_by(AuditLog.created_at.desc()).limit(50).all()
    return [{"id": l.id, "action": l.action, "entity_type": l.entity_type, "created_at": str(l.created_at)} for l in logs]
