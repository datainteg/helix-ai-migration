"""Cost service tests — rate lookup, usage rollup, guardrail enforcement."""

import uuid

from app.models.cost import OrgCostLimit
from app.services.cost_service import (
    check_within_cap,
    compute_cost,
    record_usage,
    usage_summary,
)


def test_compute_cost_known_provider():
    cost = compute_cost("anthropic", "claude-opus-4-7", 1_000_000, 1_000_000)
    assert cost == 90.0  # 15 in + 75 out per 1M


def test_compute_cost_unknown_provider_zero():
    cost = compute_cost("local", "anything", 1_000_000, 1_000_000)
    assert cost == 0.0


def test_record_usage_and_summary(db_session):
    org_id = f"org-{uuid.uuid4().hex[:8]}"
    record_usage(
        db_session,
        organization_id=org_id,
        provider_type="anthropic",
        model="claude-haiku-4-5",
        input_tokens=1000,
        output_tokens=2000,
        agent_name="analyst",
    )
    record_usage(
        db_session,
        organization_id=org_id,
        provider_type="openai",
        model="gpt-4o-mini",
        input_tokens=500,
        output_tokens=500,
        agent_name="pm",
    )
    summary = usage_summary(db_session, org_id, days=30)
    assert summary["input_tokens"] == 1500
    assert summary["output_tokens"] == 2500
    assert summary["total_cost_usd"] > 0
    providers = {p["provider"] for p in summary["by_provider"]}
    assert providers == {"anthropic", "openai"}
    agents = {a["agent"] for a in summary["by_agent"]}
    assert agents == {"analyst", "pm"}


def test_cap_disabled_when_no_row(db_session):
    org_id = f"org-{uuid.uuid4().hex[:8]}"
    allowed, reason = check_within_cap(db_session, org_id)
    assert allowed is True
    assert reason is None


def test_cap_hard_refuses_over_monthly(db_session):
    org_id = f"org-{uuid.uuid4().hex[:8]}"
    db_session.add(OrgCostLimit(organization_id=org_id, daily_usd_cap=0.0, monthly_usd_cap=0.01, enforcement="hard"))
    db_session.commit()
    # Spend more than 1 cent — Claude Opus at 1M/1M = $90.
    record_usage(
        db_session, organization_id=org_id,
        provider_type="anthropic", model="claude-opus-4-7",
        input_tokens=1_000_000, output_tokens=1_000_000,
    )
    allowed, reason = check_within_cap(db_session, org_id)
    assert allowed is False
    assert "monthly" in (reason or "")


def test_cap_soft_warns_but_allows(db_session):
    org_id = f"org-{uuid.uuid4().hex[:8]}"
    db_session.add(OrgCostLimit(organization_id=org_id, daily_usd_cap=0.01, monthly_usd_cap=0.0, enforcement="soft"))
    db_session.commit()
    record_usage(
        db_session, organization_id=org_id,
        provider_type="anthropic", model="claude-opus-4-7",
        input_tokens=1_000_000, output_tokens=0,
    )
    allowed, reason = check_within_cap(db_session, org_id)
    assert allowed is True
    assert reason is not None and "daily" in reason
