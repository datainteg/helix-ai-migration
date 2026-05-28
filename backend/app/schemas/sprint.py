"""Sprint Management Pydantic schemas.

Frontend talks to GET /api/v1/projects/{id}/sprints/* exclusively in these
shapes; mirrors `frontend/src/lib/sprints/types.ts`. Mutation endpoints
exist for create/update; seed populates via the same shapes.
"""

from typing import Any, Literal, Optional
from datetime import datetime
from pydantic import BaseModel, Field

# SC-019: free-text caps for the mutation (Create/Update) schemas below.
# Short labels get 200 chars; multi-line narrative fields get a few KB.

# H-016: the canonical set of task statuses (mirrors the frontend kanban
# `TaskStatus` union in frontend/src/lib/sprints/types.ts). Constraining the
# update schema to this Literal rejects garbage like "banana" at the schema
# layer instead of silently writing it to SprintTaskHistory.to_status.
TaskStatusLiteral = Literal[
    "backlog",
    "ready",
    "in_progress",
    "ai_processing",
    "human_review",
    "validation",
    "recon",
    "qa",
    "approved",
    "completed",
    "blocked",
]


# ── Sprint ─────────────────────────────────────────────────────────

class SprintCreate(BaseModel):
    index: int
    name: str = Field(max_length=200)
    goal: Optional[str] = Field(default=None, max_length=2000)
    status: str = "planning"
    health: str = "on-track"
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    metrics: Optional[dict] = None
    milestones: Optional[list[dict]] = None


class SprintResponse(BaseModel):
    id: str
    project_id: str
    index: int
    name: str
    goal: Optional[str] = None
    status: str
    health: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    metrics: Optional[dict] = None
    milestones: Optional[list[dict]] = None

    model_config = {"from_attributes": True}


# ── Tasks ──────────────────────────────────────────────────────────

class SprintTaskCreate(BaseModel):
    title: str = Field(max_length=500)
    type: str
    status: str = "backlog"
    priority: str = "P3"
    owner_id: Optional[str] = None
    owner_name: Optional[str] = Field(default=None, max_length=200)
    owner_kind: str = "human"
    ai_agent: Optional[str] = Field(default=None, max_length=200)
    epic_id: Optional[str] = None
    risk_level: str = "low"
    story_points: int = 0
    estimated_hours: int = 0
    actual_hours: Optional[int] = None
    validation_status: Optional[str] = None
    recon_status: Optional[str] = None
    dependency_ids: list[str] = []
    artifact_ids: list[str] = []
    blocked_reason: Optional[str] = Field(default=None, max_length=2000)


class SprintTaskResponse(SprintTaskCreate):
    id: str
    sprint_id: str

    model_config = {"from_attributes": True}


class SprintTaskUpdate(BaseModel):
    # H-016: reject unknown status strings at the schema layer.
    status: Optional[TaskStatusLiteral] = None
    priority: Optional[str] = None
    owner_id: Optional[str] = None
    owner_name: Optional[str] = Field(default=None, max_length=200)
    ai_agent: Optional[str] = Field(default=None, max_length=200)
    risk_level: Optional[str] = None
    story_points: Optional[int] = None
    actual_hours: Optional[int] = None
    validation_status: Optional[str] = None
    recon_status: Optional[str] = None
    blocked_reason: Optional[str] = Field(default=None, max_length=2000)


# ── Risks ──────────────────────────────────────────────────────────

class SprintRiskCreate(BaseModel):
    title: str = Field(max_length=500)
    category: str
    level: str
    description: Optional[str] = Field(default=None, max_length=4000)
    mitigation: Optional[str] = Field(default=None, max_length=4000)
    status: str = "open"
    ai_confidence: Optional[int] = None
    owner_id: Optional[str] = None


class SprintRiskResponse(SprintRiskCreate):
    id: str
    sprint_id: str

    model_config = {"from_attributes": True}


# ── Approvals ──────────────────────────────────────────────────────

class SprintApprovalCreate(BaseModel):
    task_id: Optional[str] = None
    kind: str
    title: str = Field(max_length=500)
    requested_by: str
    approvers: list[str] = []
    status: str = "pending"


class SprintApprovalResponse(SprintApprovalCreate):
    id: str
    sprint_id: str
    decided_at: Optional[datetime] = None
    decided_by: Optional[str] = None

    model_config = {"from_attributes": True}


class ApprovalDecision(BaseModel):
    decision: str   # "approved" | "rejected"


# ── Releases ───────────────────────────────────────────────────────

class MigrationReleaseCreate(BaseModel):
    name: str = Field(max_length=200)
    sprint_ids: list[str] = []
    stage: str = "planned"
    target_environment: str = "staging"
    scheduled_for: Optional[datetime] = None
    validation_score: int = 0
    recon_score: int = 0
    rollback_ready: bool = False
    checklist: list[dict] = []


class MigrationReleaseResponse(MigrationReleaseCreate):
    id: str
    project_id: str

    model_config = {"from_attributes": True}


# ── Mapping ────────────────────────────────────────────────────────

class MappingNodeOut(BaseModel):
    id: str
    kind: str
    label: str
    owner_id: Optional[str] = None
    agent: Optional[str] = None
    status: str
    validation_score: Optional[int] = None
    recon_score: Optional[int] = None
    risk_score: Optional[int] = None
    approval_status: str
    artifact_count: int
    position_x: float
    position_y: float

    model_config = {"from_attributes": True}


class MappingEdgeOut(BaseModel):
    id: str
    source_id: str
    target_id: str
    status: str
    label: Optional[str] = None

    model_config = {"from_attributes": True}


class MappingGraphOut(BaseModel):
    nodes: list[MappingNodeOut]
    edges: list[MappingEdgeOut]


# ── Executions ─────────────────────────────────────────────────────

class AgentExecutionOut(BaseModel):
    id: str
    agent_code: str
    task_id: Optional[str] = None
    status: str
    started_at: datetime
    duration_ms: Optional[int] = None
    retries: int
    mode: str
    log: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Velocity (derived) ─────────────────────────────────────────────

class VelocityPointOut(BaseModel):
    sprint_label: str
    planned: int
    delivered: int


class BurndownPointOut(BaseModel):
    date: str
    ideal: int
    actual: int


# ── Seed ──────────────────────────────────────────────────────────

class SeedResult(BaseModel):
    project_id: str
    sprints_created: int
    tasks_created: int
    risks_created: int
    approvals_created: int
    releases_created: int
    mapping_nodes_created: int
    mapping_edges_created: int
    executions_created: int
    duration_ms: int
