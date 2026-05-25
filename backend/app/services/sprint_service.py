"""Sprint Management service layer.

Pure CRUD + a few derived-metric helpers. Every function is org-scoped:
callers MUST pass `org_id` and the query is filtered by it. Project
ownership is enforced via `ensure_project_access` at the route layer.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.sprint import (
    Sprint, SprintTask, SprintRisk, SprintApproval,
    MigrationRelease, MappingNode, MappingEdge, AgentExecutionRecord,
)


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


def update_task_status(db: Session, org_id: str, task_id: str, new_status: str) -> SprintTask:
    task = (
        db.query(SprintTask)
        .filter(SprintTask.organization_id == org_id, SprintTask.id == task_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = new_status
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
        planned   = sum(t.story_points for t in tasks)
        delivered = sum(t.story_points for t in tasks if t.status in ("completed", "approved"))
        rows.append({"sprint_label": f"S{s.index}", "planned": planned, "delivered": delivered})
    return rows


def compute_burndown(db: Session, org_id: str, sprint_id: str) -> list[dict]:
    """Approximate burndown — straight-line ideal, actual = remaining open SP today.
    Each entry covers one day in the sprint window. Real implementation would
    pull SprintTask history; this is enough for the dashboard."""
    sp = get_sprint(db, org_id, sprint_id)
    if not sp.start_date or not sp.end_date:
        return []
    tasks = (
        db.query(SprintTask)
        .filter(SprintTask.organization_id == org_id, SprintTask.sprint_id == sprint_id)
        .all()
    )
    total = sum(t.story_points for t in tasks)
    done  = sum(t.story_points for t in tasks if t.status in ("completed", "approved"))

    days = max(1, (sp.end_date.date() - sp.start_date.date()).days + 1)
    out: list[dict] = []
    today = datetime.now(timezone.utc).date()
    for i in range(days):
        d = sp.start_date.date() + timedelta(days=i)
        ideal_remaining = round(total - (i / max(1, days - 1)) * total)
        # Linear interp between "total" at start and "total - done" today.
        if d <= today:
            actual_remaining = round(total - (done * (i / max(1, days - 1))))
        else:
            actual_remaining = total - done
        out.append({"date": d.isoformat(), "ideal": ideal_remaining, "actual": actual_remaining})
    return out
