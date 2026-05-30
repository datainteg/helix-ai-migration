"""Rate limit + API usage dashboard endpoint."""

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.dependencies import require_permission, resolve_active_org_id
from app.auth.jwt import get_current_user_id
from app.models.observability import AuditLog
from app.models.cost import OrgCostLimit
from app.services.cost_service import (
    usage_summary, daily_cost, get_cost_limit,
    list_budgets, upsert_budget, delete_budget, known_agents,
)
from app.api.audit import write_audit

router = APIRouter(tags=["usage"])


class CostLimitUpdate(BaseModel):
    daily_usd_cap: float = Field(default=0.0, ge=0.0)
    monthly_usd_cap: float = Field(default=0.0, ge=0.0)
    enforcement: str = Field(default="hard", pattern="^(hard|soft)$")


class CostBudgetUpdate(BaseModel):
    scope: str = Field(pattern="^(agent|project)$")
    scope_key: str = Field(min_length=1, max_length=100)
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


@router.get("/usage/llm/daily")
def get_daily_cost(
    days: int = 30,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Per-day USD spend for sparkline rendering."""
    org_id = resolve_active_org_id(db, user_id)
    if days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="days must be between 1 and 365")
    return daily_cost(db, org_id, days=days)


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


def _budget_dict(b) -> dict:
    return {
        "scope": b.scope,
        "scope_key": b.scope_key,
        "daily_usd_cap": b.daily_usd_cap,
        "monthly_usd_cap": b.monthly_usd_cap,
        "enforcement": b.enforcement,
    }


@router.get("/usage/budgets")
def get_budgets(
    scope: str | None = None,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Per-agent / per-project spend budgets for the active org."""
    if scope is not None and scope not in ("agent", "project"):
        raise HTTPException(status_code=400, detail="scope must be 'agent' or 'project'")
    org_id = resolve_active_org_id(db, user_id)
    return [_budget_dict(b) for b in list_budgets(db, org_id, scope)]


@router.put("/usage/budgets")
def put_budget(
    data: CostBudgetUpdate,
    request: Request,
    user_id: str = Depends(require_permission("admin:llm:write")),
    db: Session = Depends(get_db),
):
    """Create or update a per-agent / per-project budget. Caps of 0 disable
    that window for the scope."""
    org_id = resolve_active_org_id(db, user_id)
    try:
        row = upsert_budget(
            db, org_id,
            scope=data.scope, scope_key=data.scope_key,
            daily_usd_cap=data.daily_usd_cap, monthly_usd_cap=data.monthly_usd_cap,
            enforcement=data.enforcement,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    write_audit(db, org_id=org_id, actor_id=user_id, action="cost_budget_updated",
                entity_type="cost_budget", entity_id=row.id,
                meta=data.model_dump(), request=request)
    return _budget_dict(row)


@router.delete("/usage/budgets", status_code=204)
def remove_budget(
    scope: str,
    scope_key: str,
    request: Request,
    user_id: str = Depends(require_permission("admin:llm:write")),
    db: Session = Depends(get_db),
):
    org_id = resolve_active_org_id(db, user_id)
    if not delete_budget(db, org_id, scope, scope_key):
        raise HTTPException(status_code=404, detail="budget not found")
    write_audit(db, org_id=org_id, actor_id=user_id, action="cost_budget_deleted",
                entity_type="cost_budget", entity_id=f"{scope}:{scope_key}", request=request)


@router.get("/usage/agents")
def get_known_agents(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Known (AGENT_TYPES) ∪ observed agent codes — for the budget picker."""
    org_id = resolve_active_org_id(db, user_id)
    return {"agents": known_agents(db, org_id)}


@router.get("/usage/llm/export.csv")
def export_usage_csv(
    days: int = 30,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Download per-agent usage as CSV for the trailing window."""
    if days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="days must be between 1 and 365")
    org_id = resolve_active_org_id(db, user_id)
    summary = usage_summary(db, org_id, days=days)

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["agent", "cost_usd", "input_tokens", "output_tokens", "call_count"])
    for a in summary["by_agent"]:
        w.writerow([a["agent"], a["cost_usd"], a["input_tokens"], a["output_tokens"], a["call_count"]])
    w.writerow([])
    w.writerow(["TOTAL", summary["total_cost_usd"], summary["input_tokens"], summary["output_tokens"], ""])
    buf.seek(0)

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="helix-usage-{days}d.csv"'},
    )


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
