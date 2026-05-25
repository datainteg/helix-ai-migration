"""Daily cost rollup test."""

import uuid

from app.services.cost_service import daily_cost, record_usage


def test_daily_cost_zero_fills(db_session):
    org = f"org-{uuid.uuid4().hex[:8]}"
    rows = daily_cost(db_session, org, days=7)
    assert len(rows) == 7
    assert all(r["cost_usd"] == 0.0 for r in rows)
    # Last entry must be today, ISO YYYY-MM-DD format.
    assert len(rows[-1]["date"]) == 10


def test_daily_cost_records_recent_spend(db_session):
    org = f"org-{uuid.uuid4().hex[:8]}"
    record_usage(db_session, organization_id=org,
                 provider_type="anthropic", model="claude-haiku-4-5",
                 input_tokens=10_000, output_tokens=10_000)
    rows = daily_cost(db_session, org, days=7)
    assert len(rows) == 7
    total = sum(r["cost_usd"] for r in rows)
    assert total > 0
    # Spend lands in the latest bucket (today).
    assert rows[-1]["cost_usd"] > 0
