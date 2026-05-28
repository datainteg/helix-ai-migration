"""LLM cost calculation + guardrail enforcement.

The rate table (USD per 1M tokens) is hard-coded here and reflects each
provider's published pricing as of 2026-05. Operators override per-model
rates via the env var HELIX_PROVIDER_RATES_JSON if they have negotiated
custom pricing.

The numbers don't have to be perfect — they exist so cost rollups are within
the right order of magnitude. For exact billing, plug the platform's
usage-export endpoint into a downstream warehouse.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.cost import LLMUsageRecord, OrgCostLimit

logger = logging.getLogger(__name__)


# Per-1M-token rates (input, output) in USD. Conservative averages — adjust
# via HELIX_PROVIDER_RATES_JSON in .env if the operator has different pricing.
_DEFAULT_RATES: dict[str, tuple[float, float]] = {
    # OpenAI
    "openai:gpt-5":              (10.0, 30.0),
    "openai:gpt-5-mini":         (0.30, 1.20),
    "openai:gpt-4.1":            (3.0,  10.0),
    "openai:gpt-4o":             (2.5,  10.0),
    "openai:gpt-4o-mini":        (0.15, 0.60),
    # Anthropic
    "anthropic:claude-opus-4-7": (15.0, 75.0),
    "anthropic:claude-sonnet-4-6": (3.0, 15.0),
    "anthropic:claude-haiku-4-5": (0.80, 4.0),
    # Google / Gemini
    "google:gemini-3-pro":       (3.50, 10.50),
    "google:gemini-3-flash":     (0.30, 2.50),
    # DeepSeek
    "deepseek:deepseek-v4-pro":   (0.55, 2.19),
    "deepseek:deepseek-v4-flash": (0.14, 0.28),
    # OpenRouter is a meta-broker; pricing flows through whichever model is selected.
    # Vertex/Bedrock/Azure mirror their respective vendor rates (covered above).
    # Local + custom: free.
    "local:*":  (0.0, 0.0),
    "custom:*": (0.0, 0.0),
}


def _load_rates() -> dict[str, tuple[float, float]]:
    override = os.getenv("HELIX_PROVIDER_RATES_JSON")
    if not override:
        return _DEFAULT_RATES
    try:
        parsed = json.loads(override)
        return {k: (float(v[0]), float(v[1])) for k, v in parsed.items()}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Invalid HELIX_PROVIDER_RATES_JSON, using defaults: %s", exc)
        return _DEFAULT_RATES


def compute_cost(provider_type: str, model: str, input_tokens: int, output_tokens: int) -> float:
    """USD cost for a single call. Falls back to provider:* wildcard, then 0."""
    rates = _load_rates()
    key = f"{provider_type}:{model}"
    rate = rates.get(key) or rates.get(f"{provider_type}:*") or (0.0, 0.0)
    in_rate, out_rate = rate
    return (input_tokens / 1_000_000.0) * in_rate + (output_tokens / 1_000_000.0) * out_rate


def record_usage(
    db: Session,
    *,
    organization_id: str,
    provider_type: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    project_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
    agent_name: Optional[str] = None,
    step_id: Optional[str] = None,
    defer_commit: bool = False,
) -> LLMUsageRecord:
    """Persist one usage record. Cost is computed from the rate table.

    `defer_commit=True` skips the commit + refresh — caller owns the
    surrounding transaction and is responsible for `db.commit()`. This
    is the batch-friendly mode hot-path workers (BMAD executor, per-
    node activities) should use to coalesce N rows into a single
    commit and avoid the per-call connect/commit round-trip that
    saturates the worker DB pool.

    Default `defer_commit=False` keeps the original immediate-commit
    semantics so existing callers (UI-driven LLM proxies, tests) need
    no changes.
    """
    cost = compute_cost(provider_type, model, input_tokens, output_tokens)
    row = LLMUsageRecord(
        organization_id=organization_id,
        project_id=project_id,
        workflow_id=workflow_id,
        agent_name=agent_name,
        provider_type=provider_type,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
        step_id=step_id,
    )
    db.add(row)
    if defer_commit:
        db.flush()
        return row
    db.commit()
    db.refresh(row)
    return row


def record_usage_batch(
    db: Session,
    rows: list[dict],
) -> int:
    """Insert N usage records in a SINGLE commit.

    `rows` is a list of kwargs dicts shaped like `record_usage`'s
    keyword args (organization_id, provider_type, model, input_tokens,
    output_tokens, optional project_id/workflow_id/agent_name/step_id).

    Costs are computed per-row. Returns the number of rows inserted.
    Use this from the BMAD/workflow hot path where 13+ steps' worth of
    usage rows want to land in one round-trip.
    """
    if not rows:
        return 0
    objs: list[LLMUsageRecord] = []
    for r in rows:
        provider_type = r["provider_type"]
        model = r["model"]
        in_tok = r["input_tokens"]
        out_tok = r["output_tokens"]
        cost = compute_cost(provider_type, model, in_tok, out_tok)
        objs.append(LLMUsageRecord(
            organization_id=r["organization_id"],
            project_id=r.get("project_id"),
            workflow_id=r.get("workflow_id"),
            agent_name=r.get("agent_name"),
            provider_type=provider_type,
            model=model,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=cost,
            step_id=r.get("step_id"),
        ))
    db.add_all(objs)
    db.commit()
    return len(objs)


def daily_cost(db: Session, organization_id: str, days: int = 30) -> list[dict]:
    """Per-day USD spend over the trailing window. Zero-fills missing days.

    Used by the dashboard sparkline + the cost-limits side panel; cheap
    enough to compute on every request (Postgres GROUP BY date) given the
    ix_llm_usage_records_org_created index.
    """
    from sqlalchemy import cast, Date

    now = datetime.now(timezone.utc)
    # H-004: snap `since` to midnight UTC of the FIRST day in the window so
    # the SQL filter and the zero-fill loop cover exactly the same N days.
    # Previously `since = now - timedelta(days=days)` crossed day boundaries
    # (e.g. a 09:00 request excluded a usage row written at 08:30 on the
    # trailing day, while the loop still zero-filled that date) — costs near
    # the window edge appeared to vanish.
    since = (now - timedelta(days=days - 1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    # L-003: GROUP BY / ORDER BY the cast expression directly rather than the
    # "d" label. Postgres accepts a SELECT-list alias in GROUP BY, but SQLite
    # (used by the test suite) does not resolve the label in GROUP BY the same
    # way — grouping by the expression is portable across both backends.
    day_expr = cast(LLMUsageRecord.created_at, Date)
    rows = (
        db.query(
            day_expr.label("d"),
            func.coalesce(func.sum(LLMUsageRecord.cost_usd), 0.0),
        )
        .filter(LLMUsageRecord.organization_id == organization_id)
        .filter(LLMUsageRecord.created_at >= since)
        .group_by(day_expr)
        .order_by(day_expr)
        .all()
    )
    by_date = {str(r[0]): float(r[1] or 0.0) for r in rows}
    out: list[dict] = []
    cursor = since.date()
    today = now.date()
    while cursor <= today:
        key = cursor.isoformat()
        out.append({"date": key, "cost_usd": round(by_date.get(key, 0.0), 4)})
        cursor = cursor + timedelta(days=1)
    return out


def usage_summary(db: Session, organization_id: str, days: int = 30) -> dict:
    """Aggregate window: total cost + tokens + per-provider + per-agent breakdown."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    base = (
        db.query(LLMUsageRecord)
        .filter(LLMUsageRecord.organization_id == organization_id)
        .filter(LLMUsageRecord.created_at >= since)
    )

    totals = (
        base.with_entities(
            func.coalesce(func.sum(LLMUsageRecord.input_tokens), 0),
            func.coalesce(func.sum(LLMUsageRecord.output_tokens), 0),
            func.coalesce(func.sum(LLMUsageRecord.cost_usd), 0.0),
        ).one()
    )

    by_provider = (
        base.with_entities(
            LLMUsageRecord.provider_type,
            func.coalesce(func.sum(LLMUsageRecord.cost_usd), 0.0),
        )
        .group_by(LLMUsageRecord.provider_type)
        .all()
    )

    by_agent = (
        base.with_entities(
            LLMUsageRecord.agent_name,
            func.coalesce(func.sum(LLMUsageRecord.cost_usd), 0.0),
        )
        .filter(LLMUsageRecord.agent_name.isnot(None))
        .group_by(LLMUsageRecord.agent_name)
        .all()
    )

    by_project = (
        base.with_entities(
            LLMUsageRecord.project_id,
            func.coalesce(func.sum(LLMUsageRecord.cost_usd), 0.0),
        )
        .filter(LLMUsageRecord.project_id.isnot(None))
        .group_by(LLMUsageRecord.project_id)
        .all()
    )

    return {
        "window_days": days,
        "input_tokens": int(totals[0] or 0),
        "output_tokens": int(totals[1] or 0),
        "total_cost_usd": round(float(totals[2] or 0.0), 4),
        "by_provider": [
            {"provider": p, "cost_usd": round(float(c), 4)} for p, c in by_provider
        ],
        "by_agent": [
            {"agent": a, "cost_usd": round(float(c), 4)} for a, c in by_agent
        ],
        "by_project": [
            {"project_id": pid, "cost_usd": round(float(c), 4)} for pid, c in by_project
        ],
    }


def get_cost_limit(db: Session, organization_id: str) -> Optional[OrgCostLimit]:
    return db.query(OrgCostLimit).filter(OrgCostLimit.organization_id == organization_id).first()


def check_within_cap(db: Session, organization_id: str) -> tuple[bool, Optional[str]]:
    """Return (allowed, reason). reason is None when allowed.

    Hard caps refuse the workflow. Soft caps return allowed=True but with a
    reason string the caller logs as a warning.
    """
    limit = get_cost_limit(db, organization_id)
    if not limit or (limit.daily_usd_cap <= 0 and limit.monthly_usd_cap <= 0):
        return True, None

    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    daily = (
        db.query(func.coalesce(func.sum(LLMUsageRecord.cost_usd), 0.0))
        .filter(LLMUsageRecord.organization_id == organization_id)
        .filter(LLMUsageRecord.created_at >= day_start)
        .scalar()
    ) or 0.0
    monthly = (
        db.query(func.coalesce(func.sum(LLMUsageRecord.cost_usd), 0.0))
        .filter(LLMUsageRecord.organization_id == organization_id)
        .filter(LLMUsageRecord.created_at >= month_start)
        .scalar()
    ) or 0.0

    breaches = []
    if limit.daily_usd_cap > 0 and daily >= limit.daily_usd_cap:
        breaches.append(f"daily ${daily:.2f} ≥ ${limit.daily_usd_cap:.2f} cap")
    if limit.monthly_usd_cap > 0 and monthly >= limit.monthly_usd_cap:
        breaches.append(f"monthly ${monthly:.2f} ≥ ${limit.monthly_usd_cap:.2f} cap")

    if not breaches:
        return True, None
    reason = "; ".join(breaches)
    if limit.enforcement == "soft":
        return True, reason
    return False, reason
