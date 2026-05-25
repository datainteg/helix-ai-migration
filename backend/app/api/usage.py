"""Rate limit + API usage dashboard endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.dependencies import require_permission, resolve_active_org_id
from app.models.observability import AuditLog

router = APIRouter(tags=["usage"])


@router.get("/admin/usage")
def get_usage_stats(
    user_id: str = Depends(require_permission("admin:audit:read")),
    db: Session = Depends(get_db),
):
    """Per-org API usage stats: action counts over last 24h / 7d / 30d."""
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import func

    org_id = resolve_active_org_id(db, user_id)
    now = datetime.now(timezone.utc)

    def count_since(delta: timedelta) -> int:
        return (
            db.query(func.count(AuditLog.id))
            .filter(AuditLog.organization_id == org_id, AuditLog.created_at >= now - delta)
            .scalar()
        )

    def top_actions(delta: timedelta, limit: int = 10):
        return (
            db.query(AuditLog.action, func.count(AuditLog.id).label("count"))
            .filter(AuditLog.organization_id == org_id, AuditLog.created_at >= now - delta)
            .group_by(AuditLog.action)
            .order_by(func.count(AuditLog.id).desc())
            .limit(limit)
            .all()
        )

    def top_actors(delta: timedelta, limit: int = 5):
        return (
            db.query(AuditLog.actor_id, func.count(AuditLog.id).label("count"))
            .filter(AuditLog.organization_id == org_id, AuditLog.created_at >= now - delta)
            .group_by(AuditLog.actor_id)
            .order_by(func.count(AuditLog.id).desc())
            .limit(limit)
            .all()
        )

    return {
        "organization_id": org_id,
        "totals": {
            "last_24h": count_since(timedelta(hours=24)),
            "last_7d": count_since(timedelta(days=7)),
            "last_30d": count_since(timedelta(days=30)),
        },
        "top_actions_7d": [{"action": a, "count": c} for a, c in top_actions(timedelta(days=7))],
        "top_actors_7d": [{"actor_id": a, "count": c} for a, c in top_actors(timedelta(days=7))],
    }
