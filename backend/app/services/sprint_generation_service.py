"""Auto sprint generation + sprint-plan approval.

Sprints are generated from APPROVED planning artifacts only — never mock data.
The flow reuses the stage-gated machinery:

  * the SPRINT_GENERATION lifecycle stage runs the sprint-planner agent
    (John · PM) over the approved project-context/business-analysis/
    architecture/project-plan artifacts and produces a sprint-plan markdown
    artifact (reviewable like any stage artifact),
  * that markdown is parsed into structured Sprint + SprintTask rows,
  * the sprint plan is approved by approving the SPRINT_GENERATION stage
    (separation of duties + audit come for free), and
  * a sprint cannot start execution until that stage is approved.

If the agent output cannot be parsed into a usable plan, we fall back to the
canonical 6-phase migration sprint template (Source Discovery → Schema Mapping
→ ETL/Conversion → Validation → Reconciliation → Cutover/Sign-off) — standard
migration methodology, derived from the project, not random demo data.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.sprint import Sprint, SprintTask
from app.models.migration_artifact import MigrationArtifactVersion
from app.services import lifecycle_constants as LC
from app.services import stage_lifecycle_service as sl
from app.services import stage_agent_service as sa
from app.services import artifact_review_service as ar

_REQUIRED_PLANNING = [LC.PROJECT_CONTEXT, LC.BUSINESS_ANALYSIS, LC.ARCHITECTURE, LC.PROJECT_PLANNING]


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Gating ───────────────────────────────────────────────────────────
def _require_planning_approved(db: Session, org_id: str, project_id: str) -> None:
    stages = {s.stage_key: s for s in sl.get_project_lifecycle(db, org_id, project_id)}
    missing = [k for k in _REQUIRED_PLANNING
               if k not in stages or stages[k].status not in LC.STAGE_DONE_STATUSES]
    if missing:
        raise HTTPException(status_code=409,
                            detail=f"Sprint generation requires these stages approved first: {', '.join(missing)}.")


# ── Parsing ──────────────────────────────────────────────────────────
_SPRINT_HEAD = re.compile(r"^\s*(?:#{1,4}\s*)?(?:\*\*)?\s*sprint\s*\d*\s*[:\-–]?\s*(.+?)(?:\*\*)?\s*$", re.IGNORECASE)
_NUM_HEAD = re.compile(r"^\s*(\d+)[.)]\s+(.{3,80})$")
_BULLET = re.compile(r"^\s*[-*]\s+(.+?)\s*$")
_GOAL = re.compile(r"^\s*(?:#{1,6}\s*)?(?:\*\*)?\s*goal\s*[:\-]\s*(.+?)\s*$", re.IGNORECASE)


def _infer_task_type(title: str) -> str:
    t = title.lower()
    if any(w in t for w in ("reconcil", "recon")):
        return "recon"
    if any(w in t for w in ("validat", "test", "qa", "verify")):
        return "validation"
    if any(w in t for w in ("map", "mapping")):
        return "schema_mapping"
    if any(w in t for w in ("profile", "profiling", "discover", "inventory")):
        return "data_profiling"
    if any(w in t for w in ("review", "code review")):
        return "code_review"
    return "migration"


def parse_sprint_plan_to_structured_tasks(agent_output: str) -> list[dict]:
    """Best-effort parse of a sprint-plan markdown document into structured
    sprints. Returns [] if nothing usable is found (caller falls back)."""
    lines = (agent_output or "").splitlines()
    sprints: list[dict] = []
    current: dict | None = None

    def _flush():
        nonlocal current
        if current and (current["tasks"] or current["name"]):
            sprints.append(current)
        current = None

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            continue
        head = _SPRINT_HEAD.match(line)
        num = _NUM_HEAD.match(line)
        # A new sprint starts on an explicit "Sprint …" heading, or a top-level
        # numbered item that is NOT inside an existing sprint's bullet list.
        if head and ("sprint" in line.lower()):
            _flush()
            current = {"name": head.group(1).strip()[:200] or "Sprint", "goal": None, "tasks": []}
            continue
        if num and current is None:
            current = {"name": num.group(2).strip()[:200], "goal": None, "tasks": []}
            continue
        if current is None:
            continue
        g = _GOAL.match(line)
        if g and not current["goal"]:
            current["goal"] = g.group(1).strip()[:2000]
            continue
        b = _BULLET.match(line)
        if b:
            title = re.sub(r"\*\*|`", "", b.group(1)).strip()[:500]
            if title:
                current["tasks"].append({"title": title, "type": _infer_task_type(title)})
    _flush()

    # Require at least 2 sprints with tasks to trust the parse.
    usable = [s for s in sprints if s["tasks"]]
    return usable if len(usable) >= 2 else []


# Canonical migration sprint template (standard methodology, not demo data).
_DEFAULT_TEMPLATE: list[dict] = [
    {"name": "Source Discovery", "goal": "Profile and inventory the source systems.",
     "tasks": [{"title": "Profile source schema and data volumes", "type": "data_profiling", "ai_agent": "bmad-agent-architect"},
               {"title": "Inventory source objects and dependencies", "type": "migration", "ai_agent": "bmad-agent-architect"}]},
    {"name": "Schema Mapping", "goal": "Map source structures to target structures.",
     "tasks": [{"title": "Map source tables/fields to target schema", "type": "schema_mapping", "ai_agent": "bmad-agent-architect"},
               {"title": "Resolve type and constraint mismatches", "type": "schema_mapping", "ai_agent": "bmad-agent-architect"}]},
    {"name": "ETL / Code Conversion", "goal": "Generate migration code and transformation logic.",
     "tasks": [{"title": "Generate migration/ETL code", "type": "migration", "ai_agent": "bmad-agent-dev"},
               {"title": "Peer/code review of generated code", "type": "code_review", "ai_agent": "bmad-agent-dev"}]},
    {"name": "Validation", "goal": "Validate the migrated data against acceptance criteria.",
     "tasks": [{"title": "Author validation test cases", "type": "validation", "ai_agent": "qa"},
               {"title": "Execute validation and capture evidence", "type": "validation", "ai_agent": "qa"}]},
    {"name": "Reconciliation", "goal": "Reconcile source vs target and resolve mismatches.",
     "tasks": [{"title": "Run reconciliation checks (counts, sums, business rules)", "type": "recon", "ai_agent": "recon"},
               {"title": "Triage and resolve reconciliation mismatches", "type": "recon", "ai_agent": "recon"}]},
    {"name": "Cutover / Sign-off", "goal": "Execute cutover and obtain business sign-off.",
     "tasks": [{"title": "Cutover runbook and rollback plan", "type": "migration", "owner_kind": "human"},
               {"title": "Business sign-off", "type": "validation", "owner_kind": "human"}]},
]


# ── Persistence ──────────────────────────────────────────────────────
def create_sprints_and_tasks(db: Session, org_id: str, project_id: str,
                             sprint_plan_json: list[dict], artifact_id: str | None) -> list[Sprint]:
    """Persist structured sprints + tasks. Re-generation replaces prior
    generated-but-not-started sprints (planning status, created from an
    artifact) so the plan stays in sync without duplicating."""
    stale = (
        db.query(Sprint)
        .filter(Sprint.project_id == project_id, Sprint.organization_id == org_id,
                Sprint.status == "planning", Sprint.created_from_artifact_id.isnot(None))
        .all()
    )
    for sp in stale:
        db.delete(sp)   # cascade removes tasks
    db.flush()

    created: list[Sprint] = []
    for i, spec in enumerate(sprint_plan_json, start=1):
        sprint = Sprint(
            organization_id=org_id, project_id=project_id, index=i,
            name=str(spec.get("name") or f"Sprint {i}")[:200],
            goal=(spec.get("goal") or None),
            status="planning", health="on-track",
            created_from_artifact_id=artifact_id,
        )
        db.add(sprint)
        db.flush()
        for spec_task in spec.get("tasks", []):
            db.add(SprintTask(
                organization_id=org_id, sprint_id=sprint.id,
                title=str(spec_task.get("title") or "Task")[:500],
                type=spec_task.get("type") or "migration",
                status="backlog", priority=spec_task.get("priority", "P3"),
                owner_kind=spec_task.get("owner_kind", "agent" if spec_task.get("ai_agent") else "human"),
                ai_agent=spec_task.get("ai_agent"),
                risk_level=spec_task.get("risk_level", "low"),
                story_points=int(spec_task.get("story_points", 0) or 0),
                artifact_ids=[artifact_id] if artifact_id else [],
            ))
        created.append(sprint)
    db.commit()
    for s in created:
        db.refresh(s)
    return created


# ── Public flow ──────────────────────────────────────────────────────
def generate_sprints_from_approved_artifacts(db: Session, org_id: str, project_id: str,
                                             user_id: str) -> list[Sprint]:
    """Run the sprint-planner agent over approved artifacts, parse the output,
    and persist Sprint + SprintTask rows. The SPRINT_GENERATION stage is left
    under_review (its artifact must be approved before any sprint can start)."""
    _require_planning_approved(db, org_id, project_id)

    run = sa.run_stage_agent(db, org_id, project_id, LC.SPRINT_GENERATION, user_id)
    artifact_id = run.get("artifact_id")
    markdown = ""
    if artifact_id:
        versions = ar.get_artifact_versions(db, org_id, artifact_id)
        if versions:
            markdown = versions[0].content_markdown or ""

    parsed = parse_sprint_plan_to_structured_tasks(markdown)
    plan = parsed or _DEFAULT_TEMPLATE
    sprints = create_sprints_and_tasks(db, org_id, project_id, plan, artifact_id)
    sl._audit(db, org_id, user_id, "sprints_generated", project_id, LC.SPRINT_GENERATION,
              f"sprints={len(sprints)} source={'agent' if parsed else 'template'}")
    return sprints


def submit_sprint_plan_for_review(db: Session, org_id: str, project_id: str, user_id: str) -> dict:
    stage = sl.submit_stage_for_review(db, org_id, project_id, LC.SPRINT_GENERATION, None, user_id)
    return {"stage_key": LC.SPRINT_GENERATION, "status": stage.status}


def approve_sprint_plan(db: Session, org_id: str, project_id: str, user_id: str,
                        comment: str | None = None, allow_self_approval: bool = False) -> dict:
    stage = sl.approve_stage(db, org_id, project_id, LC.SPRINT_GENERATION, user_id, comment, allow_self_approval=allow_self_approval)
    return {"stage_key": LC.SPRINT_GENERATION, "status": stage.status}


def request_sprint_plan_changes(db: Session, org_id: str, project_id: str, user_id: str, comment: str) -> dict:
    stage = sl.request_stage_changes(db, org_id, project_id, LC.SPRINT_GENERATION, user_id, comment)
    return {"stage_key": LC.SPRINT_GENERATION, "status": stage.status}


def start_sprint_execution(db: Session, org_id: str, project_id: str, sprint_id: str, user_id: str) -> Sprint:
    """Activate a sprint — gated on the sprint plan (SPRINT_GENERATION stage)
    being approved/done. Execution cannot start before approval."""
    stages = {s.stage_key: s for s in sl.get_project_lifecycle(db, org_id, project_id)}
    sg = stages.get(LC.SPRINT_GENERATION)
    if not sg or sg.status not in LC.STAGE_DONE_STATUSES:
        raise HTTPException(status_code=409, detail="Sprint plan must be approved before starting sprint execution.")
    sprint = (
        db.query(Sprint)
        .filter(Sprint.id == sprint_id, Sprint.organization_id == org_id, Sprint.project_id == project_id)
        .first()
    )
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    if sprint.status == "active":
        return sprint
    sprint.status = "active"
    if not sprint.start_date:
        sprint.start_date = _now()
    sl._audit(db, org_id, user_id, "sprint_started", project_id, LC.SPRINT_EXECUTION, f"sprint={sprint_id}")
    db.commit()
    db.refresh(sprint)
    return sprint
