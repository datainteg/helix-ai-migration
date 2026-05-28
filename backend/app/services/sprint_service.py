"""Sprint Management service layer.

Pure CRUD + a few derived-metric helpers. Every function is org-scoped:
callers MUST pass `org_id` and the query is filtered by it. Project
ownership is enforced via `ensure_project_access` at the route layer.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.sprint import (
    Sprint, SprintTask, SprintRisk, SprintApproval,
    MigrationRelease, MappingNode, MappingEdge, AgentExecutionRecord,
    SprintTaskHistory,
)


# ── Create helpers ─────────────────────────────────────────────────


def _next_sprint_index(db: Session, org_id: str, project_id: str) -> int:
    """H-001: allocate the next sprint index atomically.

    The previous `count() + 1` raced: two concurrent POSTs both counted N and
    both inserted N+1. Use `SELECT max(index) ... FOR UPDATE` so the row(s)
    are locked for the duration of the transaction — the second writer blocks
    until the first commits, then sees the new max. FOR UPDATE is a no-op on
    SQLite (single-writer test path), where the partial unique index still
    backstops correctness.
    """
    q = (
        db.query(func.max(Sprint.index))
        .filter(Sprint.organization_id == org_id, Sprint.project_id == project_id)
    )
    try:
        if db.bind is not None and db.bind.dialect.name == "postgresql":
            q = q.with_for_update()
    except Exception:  # noqa: BLE001
        pass
    current_max = q.scalar()
    return (current_max or 0) + 1


def create_sprint(db: Session, org_id: str, project_id: str, data) -> Sprint:
    """Create a new sprint for a project. Index auto-increments off the
    current max(index) for the project.

    H-001: index allocation uses `max(index) FOR UPDATE` inside the
    transaction (not count()) so concurrent creators can't collide. A
    partial unique index on (organization_id, project_id, index) backstops
    this; on the rare residual IntegrityError we retry once with a freshly
    computed index.
    """
    def _attempt() -> Sprint:
        idx = data.index if getattr(data, "index", None) else _next_sprint_index(db, org_id, project_id)
        sp = Sprint(
            organization_id=org_id,
            project_id=project_id,
            index=idx,
            name=data.name,
            goal=data.goal,
            status=data.status or "planning",
            health=data.health or "on-track",
            start_date=data.start_date,
            end_date=data.end_date,
            metrics=data.metrics,
            milestones=data.milestones,
        )
        db.add(sp)
        db.commit()
        db.refresh(sp)
        return sp

    try:
        return _attempt()
    except IntegrityError:
        # Lost the race on the unique index — recompute and retry once. If the
        # caller pinned an explicit index that collides, surface a 409.
        db.rollback()
        if getattr(data, "index", None):
            raise HTTPException(
                status_code=409,
                detail=f"Sprint index {data.index} already exists for this project",
            )
        try:
            return _attempt()
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Could not allocate a unique sprint index; please retry",
            )


def create_task(db: Session, org_id: str, sprint_id: str, data) -> SprintTask:
    """Create a new task inside a sprint. Verifies sprint belongs to org."""
    get_sprint(db, org_id, sprint_id)
    task = SprintTask(
        organization_id=org_id,
        sprint_id=sprint_id,
        title=data.title,
        type=data.type,
        status=data.status or "backlog",
        priority=data.priority or "P3",
        owner_id=data.owner_id,
        owner_name=data.owner_name,
        owner_kind=data.owner_kind or "human",
        ai_agent=data.ai_agent,
        epic_id=data.epic_id,
        risk_level=data.risk_level or "low",
        story_points=data.story_points or 0,
        estimated_hours=data.estimated_hours or 0,
        actual_hours=data.actual_hours,
        validation_status=data.validation_status,
        recon_status=data.recon_status,
        dependency_ids=data.dependency_ids or [],
        artifact_ids=data.artifact_ids or [],
        blocked_reason=data.blocked_reason,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


# ── Sprints ─────────────────────────────────────────────────────────

def list_sprints(db: Session, org_id: str, project_id: str) -> list[Sprint]:
    return (
        db.query(Sprint)
        .filter(Sprint.organization_id == org_id, Sprint.project_id == project_id)
        .order_by(Sprint.index.asc())
        .all()
    )


def get_sprint(db: Session, org_id: str, sprint_id: str) -> Sprint:
    sp = (
        db.query(Sprint)
        .filter(Sprint.organization_id == org_id, Sprint.id == sprint_id)
        .first()
    )
    if not sp:
        raise HTTPException(status_code=404, detail="Sprint not found")
    return sp


def get_active_sprint(db: Session, org_id: str, project_id: str) -> Sprint | None:
    return (
        db.query(Sprint)
        .filter(
            Sprint.organization_id == org_id,
            Sprint.project_id == project_id,
            Sprint.status == "active",
        )
        .order_by(Sprint.index.asc())
        .first()
    )


# ── Tasks ──────────────────────────────────────────────────────────

def list_tasks_for_sprint(db: Session, org_id: str, sprint_id: str) -> list[SprintTask]:
    # Verify sprint belongs to org first.
    get_sprint(db, org_id, sprint_id)
    return (
        db.query(SprintTask)
        .filter(SprintTask.organization_id == org_id, SprintTask.sprint_id == sprint_id)
        .order_by(SprintTask.created_at.asc())
        .all()
    )


def update_task_status(
    db: Session,
    org_id: str,
    task_id: str,
    new_status: str,
    changed_by: str | None = None,
) -> SprintTask:
    """Update task status + append a history row.

    History rows feed `compute_burndown` so the chart reflects real
    transitions instead of a straight-line approximation.
    """
    task = (
        db.query(SprintTask)
        .filter(SprintTask.organization_id == org_id, SprintTask.id == task_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    prev_status = task.status
    task.status = new_status
    db.add(SprintTaskHistory(
        organization_id=org_id,
        sprint_id=task.sprint_id,
        task_id=task.id,
        from_status=prev_status,
        to_status=new_status,
        story_points=task.story_points,
        changed_by=changed_by,
    ))
    db.commit()
    db.refresh(task)
    return task


# ── Risks ──────────────────────────────────────────────────────────

def list_risks_for_sprint(db: Session, org_id: str, sprint_id: str) -> list[SprintRisk]:
    get_sprint(db, org_id, sprint_id)
    return (
        db.query(SprintRisk)
        .filter(SprintRisk.organization_id == org_id, SprintRisk.sprint_id == sprint_id)
        .all()
    )


# ── Approvals ──────────────────────────────────────────────────────

def list_approvals_for_sprint(db: Session, org_id: str, sprint_id: str) -> list[SprintApproval]:
    get_sprint(db, org_id, sprint_id)
    return (
        db.query(SprintApproval)
        .filter(SprintApproval.organization_id == org_id, SprintApproval.sprint_id == sprint_id)
        .order_by(SprintApproval.created_at.desc())
        .all()
    )


def decide_approval(db: Session, org_id: str, approval_id: str, decision: str, decided_by: str) -> SprintApproval:
    if decision not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="decision must be 'approved' or 'rejected'")
    ap = (
        db.query(SprintApproval)
        .filter(SprintApproval.organization_id == org_id, SprintApproval.id == approval_id)
        .first()
    )
    if not ap:
        raise HTTPException(status_code=404, detail="Approval not found")
    ap.status = decision
    ap.decided_at = datetime.now(timezone.utc)
    ap.decided_by = decided_by
    db.commit()
    db.refresh(ap)
    return ap


# ── Releases ───────────────────────────────────────────────────────

def list_releases(db: Session, org_id: str, project_id: str) -> list[MigrationRelease]:
    return (
        db.query(MigrationRelease)
        .filter(MigrationRelease.organization_id == org_id, MigrationRelease.project_id == project_id)
        .order_by(MigrationRelease.scheduled_for.asc().nullslast())
        .all()
    )


# ── Mapping graph ───────────────────────────────────────────────────

def get_mapping_graph(db: Session, org_id: str, project_id: str) -> tuple[list[MappingNode], list[MappingEdge]]:
    nodes = (
        db.query(MappingNode)
        .filter(MappingNode.organization_id == org_id, MappingNode.project_id == project_id)
        .all()
    )
    edges = (
        db.query(MappingEdge)
        .filter(MappingEdge.organization_id == org_id, MappingEdge.project_id == project_id)
        .all()
    )
    return nodes, edges


# ── Executions ─────────────────────────────────────────────────────

def list_executions(db: Session, org_id: str, project_id: str, limit: int = 50) -> list[AgentExecutionRecord]:
    return (
        db.query(AgentExecutionRecord)
        .filter(
            AgentExecutionRecord.organization_id == org_id,
            AgentExecutionRecord.project_id == project_id,
        )
        .order_by(AgentExecutionRecord.started_at.desc())
        .limit(limit)
        .all()
    )


# ── Derived: velocity + burndown ────────────────────────────────────

def compute_velocity(db: Session, org_id: str, project_id: str) -> list[dict]:
    sprints = list_sprints(db, org_id, project_id)
    rows: list[dict] = []
    for s in sprints:
        tasks = (
            db.query(SprintTask)
            .filter(SprintTask.organization_id == org_id, SprintTask.sprint_id == s.id)
            .all()
        )
        # H-010: story_points is nullable; coalesce to 0 so a single
        # NULL row doesn't raise TypeError and 500 the analytics endpoint.
        planned   = sum((t.story_points or 0) for t in tasks)
        delivered = sum((t.story_points or 0) for t in tasks if t.status in ("completed", "approved"))
        rows.append({"sprint_label": f"S{s.index}", "planned": planned, "delivered": delivered})
    return rows


def compute_burndown(db: Session, org_id: str, sprint_id: str) -> list[dict]:
    """Per-day burndown computed from real `sprint_task_history` transitions.

    For each day in the sprint window:
      - ideal  = straight line from `total_sp` on day 0 → 0 on last day.
      - actual = `total_sp` minus the cumulative story points of tasks that
                 transitioned into a done-bucket (completed | approved) on
                 or before that day's end.

    Falls back to a straight-line estimate if no history rows exist yet
    (e.g. brand-new sprint pre-status-changes)."""
    sp = get_sprint(db, org_id, sprint_id)
    if not sp.start_date or not sp.end_date:
        return []

    tasks = (
        db.query(SprintTask)
        .filter(SprintTask.organization_id == org_id, SprintTask.sprint_id == sprint_id)
        .all()
    )
    total = sum((t.story_points or 0) for t in tasks)  # H-010: NULL-safe
    if total == 0:
        return []

    history = (
        db.query(SprintTaskHistory)
        .filter(
            SprintTaskHistory.organization_id == org_id,
            SprintTaskHistory.sprint_id == sprint_id,
            SprintTaskHistory.to_status.in_(("completed", "approved")),
        )
        .order_by(SprintTaskHistory.created_at.asc())
        .all()
    )

    days = max(1, (sp.end_date.date() - sp.start_date.date()).days + 1)
    today = datetime.now(timezone.utc).date()

    # Build cumulative-by-day series. Track latest done-state per task so we
    # don't double-count if a task bounced through done → review → done.
    sp_per_task_at_day: dict[str, dict] = {}
    for h in history:
        if not h.created_at:
            continue
        d = h.created_at.date().isoformat()
        sp_per_task_at_day.setdefault(d, {})[h.task_id] = h.story_points or 0  # H-010

    # Use history fallback if it's empty
    if not history:
        done = sum((t.story_points or 0) for t in tasks if t.status in ("completed", "approved"))  # H-010
        out: list[dict] = []
        for i in range(days):
            d = sp.start_date.date() + timedelta(days=i)
            ideal_remaining = round(total - (i / max(1, days - 1)) * total)
            # M-014: future days carry no actual value (None) so the chart
            # stops the actual line at today instead of projecting forward.
            if d <= today:
                actual_remaining = round(total - (done * (i / max(1, days - 1))))
            else:
                actual_remaining = None
            out.append({"date": d.isoformat(), "ideal": ideal_remaining, "actual": actual_remaining})
        return out

    out: list[dict] = []
    completed_by_task: dict[str, int] = {}
    for i in range(days):
        d = sp.start_date.date() + timedelta(days=i)
        # Apply any transitions logged on or before this day
        for log_d_iso, deltas in sp_per_task_at_day.items():
            if log_d_iso <= d.isoformat():
                completed_by_task.update(deltas)
        cumulative_done = sum(completed_by_task.values())
        ideal_remaining = round(total - (i / max(1, days - 1)) * total)
        # M-014: the previous `... if d <= today else ...` had identical
        # branches, so the actual line marched into the future as if today's
        # progress applied to every future day. Emit `None` for future days so
        # the chart doesn't draw a fabricated "predicted past" beyond today.
        actual_remaining = (total - cumulative_done) if d <= today else None
        out.append({"date": d.isoformat(), "ideal": ideal_remaining, "actual": actual_remaining})
    return out
