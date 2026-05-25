"""LLM cost tracking models.

Two tables:
  llm_usage_records   one row per LLM call (token counts + computed $)
  org_cost_limits     per-org guardrails (daily + monthly USD cap)

Every BMAD step writes a usage row through `cost_service.record_usage`. The
dashboard + per-project drill-down read aggregates from this table; the
workflow service consults it before starting a new run so a workflow that
would breach the org cap is rejected up-front.
"""

from sqlalchemy import Column, String, DateTime, Integer, Float, ForeignKey

from app.models.base import BaseModel


class LLMUsageRecord(BaseModel):
    """One row per LLM call. Wide table; indexes on the most common filters."""

    __tablename__ = "llm_usage_records"

    organization_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), nullable=True, index=True)
    workflow_id = Column(String(255), nullable=True, index=True)
    agent_name = Column(String(100), nullable=True, index=True)
    provider_type = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    input_tokens = Column(Integer, default=0, nullable=False)
    output_tokens = Column(Integer, default=0, nullable=False)
    cost_usd = Column(Float, default=0.0, nullable=False)
    # Optional FK to the workflow_step that produced this call. NULL when the
    # call is outside a workflow context (test_connection, manual playground).
    step_id = Column(String(36), ForeignKey("workflow_steps.id"), nullable=True)


class OrgCostLimit(BaseModel):
    """Per-org cost cap. One row per org or none (cap disabled)."""

    __tablename__ = "org_cost_limits"

    organization_id = Column(String(36), nullable=False, unique=True, index=True)
    # USD. 0 = disabled. Negative not allowed (schema enforces via service).
    daily_usd_cap = Column(Float, default=0.0, nullable=False)
    monthly_usd_cap = Column(Float, default=0.0, nullable=False)
    # Soft mode: emit warning event but allow workflow to proceed. Hard mode
    # (default): refuse workflow start once the cap is exceeded.
    enforcement = Column(String(20), default="hard", nullable=False)
