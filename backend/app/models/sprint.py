"""Sprint Management domain models.

All sprint data is org-scoped AND project-scoped — the same migration
project can run different sprint plans, but every row is reachable only
via the owning organization (cross-tenant lookups are blocked at the
service layer).

Tables:
  - sprints              — top-level sprint container
  - sprint_tasks         — kanban tasks (one row per card)
  - sprint_risks         — risk register entries
  - sprint_approvals     — pending / completed approval items
  - migration_releases   — release calendar + checklist
  - mapping_nodes        — execution mapping canvas nodes
  - mapping_edges        — execution mapping canvas edges
  - agent_executions     — recent agent activity (live exec view)

Burndown + velocity are derived at read-time from sprint_tasks history
to avoid duplicating state; see SprintService.get_burndown.
"""

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class Sprint(BaseModel):
    __tablename__ = "sprints"

    organization_id = Column(String(36), nullable=False, index=True)
    project_id      = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    index           = Column(Integer, nullable=False)       # 1, 2, 3, ...
    name            = Column(String(255), nullable=False)
    goal            = Column(Text, nullable=True)
    status          = Column(String(40), default="planning", nullable=False)   # planning|active|review|completed|cancelled
    health          = Column(String(40), default="on-track", nullable=False)   # on-track|at-risk|off-track|blocked
    start_date      = Column(DateTime(timezone=True), nullable=True)
    end_date        = Column(DateTime(timezone=True), nullable=True)
    # Snapshot metrics — refreshed by SprintService when tasks change.
    metrics         = Column(JSON, nullable=True)
    # Milestones live as JSON inline (small, ordered list).
    milestones      = Column(JSON, nullable=True)

    # ── Stage-gated lifecycle additions ─────────────────────────────────
    sprint_alias                = Column(String(40), nullable=True)   # e.g. HXM-482913-S1
    progress_percent            = Column(Integer, default=0, nullable=False, server_default="0")
    validation_progress_percent = Column(Integer, default=0, nullable=False, server_default="0")
    recon_progress_percent      = Column(Integer, default=0, nullable=False, server_default="0")
    risk_level                  = Column(String(20), nullable=True)
    created_from_artifact_id    = Column(String(36), nullable=True)   # sprint-plan artifact it was generated from
    approved_by_user_id         = Column(String(36), nullable=True)
    approved_at                 = Column(DateTime(timezone=True), nullable=True)

    tasks      = relationship("SprintTask",     back_populates="sprint", cascade="all, delete-orphan")
    risks      = relationship("SprintRisk",     back_populates="sprint", cascade="all, delete-orphan")
    approvals  = relationship("SprintApproval", back_populates="sprint", cascade="all, delete-orphan")


class SprintTask(BaseModel):
    __tablename__ = "sprint_tasks"

    organization_id = Column(String(36), nullable=False, index=True)
    sprint_id       = Column(String(36), ForeignKey("sprints.id", ondelete="CASCADE"), nullable=False, index=True)
    title           = Column(String(500), nullable=False)
    type            = Column(String(40), nullable=False)   # migration|validation|recon|...
    status          = Column(String(40), default="backlog", nullable=False)
    priority        = Column(String(4),  default="P3",     nullable=False)
    owner_id        = Column(String(36), nullable=True)
    owner_name      = Column(String(255), nullable=True)
    owner_kind      = Column(String(20), default="human", nullable=False)   # human|agent
    ai_agent        = Column(String(64), nullable=True)
    epic_id         = Column(String(64), nullable=True)
    risk_level      = Column(String(20), default="low",    nullable=False)
    story_points    = Column(Integer,    default=0,        nullable=False)
    estimated_hours = Column(Integer,    default=0,        nullable=False)
    actual_hours    = Column(Integer,    nullable=True)
    validation_status = Column(String(20), nullable=True)
    recon_status      = Column(String(20), nullable=True)
    dependency_ids  = Column(JSON, nullable=True)          # list[str]
    artifact_ids    = Column(JSON, nullable=True)          # list[str]
    blocked_reason  = Column(Text, nullable=True)

    sprint = relationship("Sprint", back_populates="tasks")


class SprintRisk(BaseModel):
    __tablename__ = "sprint_risks"

    organization_id = Column(String(36), nullable=False, index=True)
    sprint_id       = Column(String(36), ForeignKey("sprints.id", ondelete="CASCADE"), nullable=False, index=True)
    title           = Column(String(500), nullable=False)
    category        = Column(String(40), nullable=False)   # data|validation|recon|deployment|compliance|security
    level           = Column(String(20), nullable=False)   # low|med|high|critical
    description     = Column(Text, nullable=True)
    mitigation      = Column(Text, nullable=True)
    status          = Column(String(20), default="open", nullable=False)   # open|mitigating|accepted|closed
    ai_confidence   = Column(Integer, nullable=True)
    owner_id        = Column(String(36), nullable=True)

    sprint = relationship("Sprint", back_populates="risks")


class SprintApproval(BaseModel):
    __tablename__ = "sprint_approvals"

    organization_id = Column(String(36), nullable=False, index=True)
    sprint_id       = Column(String(36), ForeignKey("sprints.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id         = Column(String(36), ForeignKey("sprint_tasks.id", ondelete="SET NULL"), nullable=True)
    kind            = Column(String(40), nullable=False)   # milestone|release|code_review|validation_override
    title           = Column(String(500), nullable=False)
    requested_by    = Column(String(255), nullable=False)
    approvers       = Column(JSON, nullable=True)          # list[str]
    status          = Column(String(20), default="pending", nullable=False)
    decided_at      = Column(DateTime(timezone=True), nullable=True)
    decided_by      = Column(String(36), nullable=True)

    sprint = relationship("Sprint", back_populates="approvals")


class MigrationRelease(BaseModel):
    __tablename__ = "migration_releases"

    organization_id    = Column(String(36), nullable=False, index=True)
    project_id         = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name               = Column(String(255), nullable=False)
    sprint_ids         = Column(JSON, nullable=True)        # list[str]
    stage              = Column(String(40), default="planned", nullable=False)
    target_environment = Column(String(20), default="staging", nullable=False)
    scheduled_for      = Column(DateTime(timezone=True), nullable=True)
    validation_score   = Column(Integer, default=0, nullable=False)
    recon_score        = Column(Integer, default=0, nullable=False)
    rollback_ready     = Column(Boolean, default=False, nullable=False)
    checklist          = Column(JSON, nullable=True)        # list[{id,label,done,owner}]


class MappingNode(BaseModel):
    __tablename__ = "sprint_mapping_nodes"

    organization_id   = Column(String(36), nullable=False, index=True)
    project_id        = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    kind              = Column(String(40), nullable=False)
    label             = Column(String(255), nullable=False)
    owner_id          = Column(String(36), nullable=True)
    agent             = Column(String(64), nullable=True)
    status            = Column(String(40), default="pending", nullable=False)
    validation_score  = Column(Integer, nullable=True)
    recon_score       = Column(Integer, nullable=True)
    risk_score        = Column(Integer, nullable=True)
    approval_status   = Column(String(20), default="not_required", nullable=False)
    artifact_count    = Column(Integer, default=0, nullable=False)
    position_x        = Column(Float, default=0, nullable=False)
    position_y        = Column(Float, default=0, nullable=False)


class MappingEdge(BaseModel):
    __tablename__ = "sprint_mapping_edges"

    organization_id = Column(String(36), nullable=False, index=True)
    project_id      = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id       = Column(String(36), ForeignKey("sprint_mapping_nodes.id", ondelete="CASCADE"), nullable=False)
    target_id       = Column(String(36), ForeignKey("sprint_mapping_nodes.id", ondelete="CASCADE"), nullable=False)
    status          = Column(String(20), default="pending", nullable=False)
    label           = Column(String(255), nullable=True)


class AgentExecutionRecord(BaseModel):
    __tablename__ = "sprint_agent_executions"

    organization_id = Column(String(36), nullable=False, index=True)
    project_id      = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_code      = Column(String(64), nullable=False)
    task_id         = Column(String(36), nullable=True)
    status          = Column(String(20), default="queued", nullable=False)   # running|succeeded|failed|retrying|queued|cancelled
    started_at      = Column(DateTime(timezone=True), nullable=False)
    duration_ms     = Column(Integer, nullable=True)
    retries         = Column(Integer, default=0, nullable=False)
    mode            = Column(String(10), default="llm", nullable=False)
    log             = Column(Text, nullable=True)


class SprintTaskHistory(BaseModel):
    """Append-only audit of task status transitions.

    One row written every time `update_task_status` runs. Lets burndown
    reconstruct from real timestamps instead of straight-line interp.
    Indexed on (sprint_id, created_at) so the burndown query is a
    single seek.
    """
    __tablename__ = "sprint_task_history"

    organization_id = Column(String(36), nullable=False, index=True)
    sprint_id       = Column(String(36), ForeignKey("sprints.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id         = Column(String(36), ForeignKey("sprint_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    from_status     = Column(String(40), nullable=True)
    to_status       = Column(String(40), nullable=False)
    story_points    = Column(Integer, default=0, nullable=False)
    changed_by      = Column(String(36), nullable=True)
