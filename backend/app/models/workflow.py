"""Workflow persistence models — workflow_runs and workflow_steps."""

from sqlalchemy import Column, String, Text, ForeignKey, Integer, DateTime
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class WorkflowRun(BaseModel):
    """Tracks a complete BMAD workflow execution."""

    __tablename__ = "workflow_runs"

    organization_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), nullable=False, index=True)
    requirement_id = Column(String(36), nullable=False)
    workflow_id = Column(String(255), nullable=False, unique=True)
    run_id = Column(String(255), nullable=True)
    status = Column(String(50), default="pending", nullable=False)
    mode = Column(String(50), nullable=False)  # "temporal" or "local_fallback"

    steps = relationship("WorkflowStep", back_populates="workflow_run", cascade="all, delete-orphan")


class WorkflowStep(BaseModel):
    """Tracks each agent step within a workflow run."""

    __tablename__ = "workflow_steps"

    workflow_run_id = Column(String(36), ForeignKey("workflow_runs.id"), nullable=False)
    agent_name = Column(String(100), nullable=False)
    step_order = Column(Integer, nullable=False)
    status = Column(String(50), default="pending", nullable=False)
    raw_output = Column(Text, nullable=True)
    parsed_output_json = Column(Text, nullable=True)  # JSON string — JSONB on PostgreSQL, Text on SQLite
    provider_name = Column(String(100), nullable=True)
    model_name = Column(String(100), nullable=True)
    prompt_version = Column(String(20), nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    workflow_run = relationship("WorkflowRun", back_populates="steps")
