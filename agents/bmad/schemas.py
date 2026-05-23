from typing import Literal

from pydantic import BaseModel, Field


class RiskItem(BaseModel):
    title: str
    severity: Literal["low", "medium", "high", "critical"]
    impact: str
    mitigation: str


class BusinessAnalystOutput(BaseModel):
    summary: str
    business_goals: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    risks: list[RiskItem] = Field(default_factory=list)


class ArchitectOutput(BaseModel):
    architecture_summary: str
    source_systems: list[str] = Field(default_factory=list)
    target_systems: list[str] = Field(default_factory=list)
    integration_points: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    risks: list[RiskItem] = Field(default_factory=list)


class ValidationPlanOutput(BaseModel):
    validation_strategy: str
    checks: list[str] = Field(default_factory=list)
    reconciliation_approach: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    risks: list[RiskItem] = Field(default_factory=list)


class ApprovalGateOutput(BaseModel):
    approval_required: bool
    approval_reason: str
    next_step: str


class BMADFinalOutput(BaseModel):
    business_analysis: BusinessAnalystOutput
    architecture: ArchitectOutput
    validation_plan: ValidationPlanOutput
    approval_gate: ApprovalGateOutput
    status: str
