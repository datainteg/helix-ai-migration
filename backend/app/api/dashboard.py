"""Org-wide dashboard aggregator.

One endpoint that returns every metric the /dashboard page needs in a single
round-trip. Replaces the client-side `Promise.all([projects, workflows])`
fan-out + adds real validation pass-rate + recon score.

Computed at request time. The volumes targeted (<= 200 projects per org,
<= a few thousand validation results) are fine for a synchronous query path;
add a materialised view + 15s cache if this becomes hot.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_read_db as get_db
from app.auth.dependencies import get_current_organization_id
from app.models.project import Project
from app.models.workflow import WorkflowRun
from app.models.validation import ValidationResult, ValidationRun, ReconResult, ReconRun

router = APIRouter(tags=["dashboard"])


class DashboardProjects(BaseModel):
    active: int
    archived: int
    by_status: dict[str, int]


class DashboardWorkflows(BaseModel):
    running: int
    pending: int
    completed: int
    failed: int
    total: int


class DashboardValidation(BaseModel):
    total_results: int
    passed: int
    # `None` when there are no validation results — caller must handle.
    pass_rate: float | None = None


class DashboardRecon(BaseModel):
    total_results: int
    clean: int
    score: float | None = None


class DashboardStats(BaseModel):
    """Single-call aggregator response for the Operations Overview dashboard.

    Replaces the hand-built dict so OpenAPI documents every field;
    consumers can generate types instead of guessing at the shape.
    """

    projects: DashboardProjects
    workflows: DashboardWorkflows
    validation: DashboardValidation
    recon: DashboardRecon
    has_any_data: bool


class ActivityItem(BaseModel):
    workflow_id: str
    project_id: str
    project_name: str | None = None
    kind: str
    status: str
    created_at: str | None = None


class ValidationBreakdown(BaseModel):
    """Validation result counts by status (passed / failed / warning / …)."""
    by_status: dict[str, int]
    total: int


_RUNNING = {"running", "started", "in_progress"}
_PENDING = {"pending", "awaiting_approval"}
_DONE = {"completed", "approved"}
_FAILED = {"failed", "rejected", "expired"}


@router.get("/dashboard/stats", response_model=DashboardStats)
def dashboard_stats(
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
) -> DashboardStats:
    """Single-call aggregator for the Operations Overview dashboard."""
    # ── Projects ──
    projects = (
        db.query(Project.status, func.count(Project.id))
        .filter(Project.organization_id == org_id)
        .group_by(Project.status)
        .all()
    )
    proj_counts: dict[str, int] = {s or "active": c for s, c in projects}
    active_projects = sum(c for s, c in proj_counts.items() if s not in ("archived", "deleted"))
    archived_projects = proj_counts.get("archived", 0)

    # ── Workflow runs (by bucket) ──
    runs = (
        db.query(WorkflowRun.status, func.count(WorkflowRun.id))
        .filter(WorkflowRun.organization_id == org_id)
        .group_by(WorkflowRun.status)
        .all()
    )
    running = sum(c for s, c in runs if (s or "").lower() in _RUNNING)
    pending = sum(c for s, c in runs if (s or "").lower() in _PENDING)
    completed = sum(c for s, c in runs if (s or "").lower() in _DONE)
    failed = sum(c for s, c in runs if (s or "").lower() in _FAILED)
    total_workflows = sum(c for _, c in runs)

    # ── Validation pass rate (org-wide) ──
    # Join ValidationResult → ValidationRun → Project to scope by org.
    v_total = (
        db.query(func.count(ValidationResult.id))
        .join(ValidationRun, ValidationResult.run_id == ValidationRun.id)
        .join(Project, ValidationRun.project_id == Project.id)
        .filter(Project.organization_id == org_id)
        .scalar()
        or 0
    )
    v_passed = (
        db.query(func.count(ValidationResult.id))
        .join(ValidationRun, ValidationResult.run_id == ValidationRun.id)
        .join(Project, ValidationRun.project_id == Project.id)
        .filter(Project.organization_id == org_id, ValidationResult.status == "passed")
        .scalar()
        or 0
    )
    validation_pass_rate = round((v_passed / v_total) * 100, 1) if v_total > 0 else None

    # ── Recon score (mismatch_count == 0 over total) ──
    r_total = (
        db.query(func.count(ReconResult.id))
        .join(ReconRun, ReconResult.run_id == ReconRun.id)
        .join(Project, ReconRun.project_id == Project.id)
        .filter(Project.organization_id == org_id)
        .scalar()
        or 0
    )
    r_clean = (
        db.query(func.count(ReconResult.id))
        .join(ReconRun, ReconResult.run_id == ReconRun.id)
        .join(Project, ReconRun.project_id == Project.id)
        .filter(Project.organization_id == org_id, ReconResult.mismatch_count == 0)
        .scalar()
        or 0
    )
    recon_score = round((r_clean / r_total) * 100, 1) if r_total > 0 else None

    has_any_data = (
        active_projects > 0
        or archived_projects > 0
        or total_workflows > 0
        or v_total > 0
        or r_total > 0
    )

    return DashboardStats(
        projects=DashboardProjects(
            active=active_projects,
            archived=archived_projects,
            by_status=proj_counts,
        ),
        workflows=DashboardWorkflows(
            running=running,
            pending=pending,
            completed=completed,
            failed=failed,
            total=total_workflows,
        ),
        validation=DashboardValidation(
            total_results=v_total,
            passed=v_passed,
            pass_rate=validation_pass_rate,
        ),
        recon=DashboardRecon(
            total_results=r_total,
            clean=r_clean,
            score=recon_score,
        ),
        has_any_data=has_any_data,
    )


@router.get("/dashboard/activity", response_model=list[ActivityItem])
def dashboard_activity(
    limit: int = 12,
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
) -> list[ActivityItem]:
    """Most recent workflow runs across the org (feeds the dashboard activity
    feed + projects-requiring-attention). Joined to project name."""
    limit = max(1, min(limit, 50))
    rows = (
        db.query(WorkflowRun, Project.name)
        .outerjoin(Project, WorkflowRun.project_id == Project.id)
        .filter(WorkflowRun.organization_id == org_id)
        .order_by(WorkflowRun.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        ActivityItem(
            workflow_id=run.workflow_id,
            project_id=run.project_id,
            project_name=pname,
            kind=run.kind or "bmad",
            status=run.status,
            created_at=str(run.created_at) if run.created_at else None,
        )
        for run, pname in rows
    ]


@router.get("/dashboard/validation-breakdown", response_model=ValidationBreakdown)
def dashboard_validation_breakdown(
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
) -> ValidationBreakdown:
    """Validation results grouped by status, org-wide (feeds the dashboard
    'Validation outcomes' panel)."""
    rows = (
        db.query(ValidationResult.status, func.count(ValidationResult.id))
        .join(ValidationRun, ValidationResult.run_id == ValidationRun.id)
        .join(Project, ValidationRun.project_id == Project.id)
        .filter(Project.organization_id == org_id)
        .group_by(ValidationResult.status)
        .all()
    )
    by_status = {(s or "unknown"): int(c) for s, c in rows}
    return ValidationBreakdown(by_status=by_status, total=sum(by_status.values()))
