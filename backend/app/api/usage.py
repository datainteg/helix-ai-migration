"""Rate limit + API usage dashboard endpoint."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.dependencies import require_permission, resolve_active_org_id
from app.auth.jwt import get_current_user_id
from app.models.observability import AuditLog
from app.models.cost import OrgCostLimit
from app.services.cost_service import usage_summary, get_cost_limit
from app.api.audit import write_audit

router = APIRouter(tags=["usage"])


class CostLimitUpdate(BaseModel):
    daily_usd_cap: float = Field(default=0.0, ge=0.0)
    monthly_usd_cap: float = Field(default=0.0, ge=0.0)
    enforcement: str = Field(default="hard", pattern="^(hard|soft)$")


@router.get("/usage/llm")
def get_llm_usage(
    days: int = 30,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Per-org LLM cost rollup: total tokens, total USD, breakdown by
    provider/agent/project over the trailing `days` window."""
    org_id = resolve_active_org_id(db, user_id)
    if days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="days must be between 1 and 365")
    return usage_summary(db, org_id, days=days)


@router.get("/usage/cost-limit")
def get_cost_limit_endpoint(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    org_id = resolve_active_org_id(db, user_id)
    limit = get_cost_limit(db, org_id)
    if not limit:
        return {"daily_usd_cap": 0.0, "monthly_usd_cap": 0.0, "enforcement": "hard", "configured": False}
    return {
        "daily_usd_cap": limit.daily_usd_cap,
        "monthly_usd_cap": limit.monthly_usd_cap,
        "enforcement": limit.enforcement,
        "configured": True,
    }


@router.put("/usage/cost-limit")
def update_cost_limit(
    data: CostLimitUpdate,
    request: Request,
    user_id: str = Depends(require_permission("admin:llm:write")),
    db: Session = Depends(get_db),
):
    """Upsert the org's cost cap. Set both caps to 0 to disable enforcement."""
    org_id = resolve_active_org_id(db, user_id)
    limit = get_cost_limit(db, org_id)
    if limit is None:
        limit = OrgCostLimit(organization_id=org_id)
        db.add(limit)
    limit.daily_usd_cap = data.daily_usd_cap
    limit.monthly_usd_cap = data.monthly_usd_cap
    limit.enforcement = data.enforcement
    db.commit()
    db.refresh(limit)
    write_audit(db, org_id=org_id, actor_id=user_id, action="cost_limit_updated",
                entity_type="org_cost_limit", entity_id=limit.id,
                meta=data.model_dump(), request=request)
    return {
        "daily_usd_cap": limit.daily_usd_cap,
        "monthly_usd_cap": limit.monthly_usd_cap,
        "enforcement": limit.enforcement,
        "configured": True,
    }


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
