"""Stage-gated migration lifecycle models.

`migration_stages` — one row per lifecycle stage per project (the state
machine). `stage_transition_logs` — an append-only domain audit of every
status change (separate from the security `audit_logs`).
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey, UniqueConstraint, Index

from app.models.base import BaseModel


class MigrationStage(BaseModel):
    __tablename__ = "migration_stages"

    organization_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    stage_key = Column(String(40), nullable=False, index=True)   # e.g. PROJECT_CONTEXT
    stage_name = Column(String(120), nullable=False)
    stage_order = Column(Integer, nullable=False)
    status = Column(String(30), default="not_started", nullable=False, index=True)
    assigned_agent = Column(String(80), nullable=True)           # llm_agent_mappings code / sentinel
    is_optional = Column(Boolean, default=False, nullable=False)
    # Lifecycle timestamps.
    started_at = Column(DateTime(timezone=True), nullable=True)
    generated_at = Column(DateTime(timezone=True), nullable=True)
    submitted_for_review_at = Column(DateTime(timezone=True), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejected_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    # The artifact currently under review / approved for this stage.
    current_artifact_id = Column(String(36), nullable=True)
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)

    __table_args__ = (
        UniqueConstraint("project_id", "stage_key", name="uq_migration_stage_project_key"),
    )


class StageTransitionLog(BaseModel):
    __tablename__ = "stage_transition_logs"

    organization_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    stage_id = Column(String(36), ForeignKey("migration_stages.id", ondelete="CASCADE"), nullable=False, index=True)
    from_status = Column(String(30), nullable=True)
    to_status = Column(String(30), nullable=False)
    action = Column(String(40), nullable=False)                  # start|generate|submit|approve|reject|request_changes|resubmit|skip|advance|fail
    actor_type = Column(String(20), nullable=False)              # user|agent|system
    actor_id = Column(String(36), nullable=True)
    comment = Column(Text, nullable=True)
