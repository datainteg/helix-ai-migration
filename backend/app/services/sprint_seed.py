"""Seed example Sprint Management data for a project.

Idempotent at the org+project level: deletes any existing rows for the
target project before inserting fresh ones, so re-running the seed
gives the same demo state. Designed to be callable both from:
  - HTTP POST /api/v1/projects/{id}/sprints/seed (admin button)
  - scripts/seed.py CLI for ops + first-deploy bootstrap.

The data here is the canonical "Oracle GL → Snowflake" sample —
same content the frontend used to ship as mock. After seeding the
frontend reads from the DB and the mock module can be deleted.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.sprint import (
    Sprint, SprintTask, SprintRisk, SprintApproval,
    MigrationRelease, MappingNode, MappingEdge, AgentExecutionRecord,
)


SPRINT_PLAN = [
    {"name": "Source Discovery",      "goal": "Catalog Oracle GL schema + identify downstream dependencies",   "status": "completed", "health": "on-track"},
    {"name": "Schema Mapping",        "goal": "Map source/target schemas with type and constraint resolution", "status": "completed", "health": "on-track"},
    {"name": "ETL Conversion",        "goal": "Generate Snowflake DDL + Databricks notebooks via Amelia",       "status": "active",    "health": "at-risk"},
    {"name": "Validation & Recon",    "goal": "Run end-to-end validation + reconciliation gates",               "status": "planning",  "health": "on-track"},
    {"name": "Production Cutover",    "goal": "Cutover plan, dry-run, production deployment",                   "status": "planning",  "health": "on-track"},
]

TASK_TEMPLATES = [
    ("Profile GL_LEDGER source rows",        "data_profiling", "Mary"),
    ("Map GL_TRANS → trans_fact schema",     "schema_mapping", "Winston"),
    ("Convert MERGE PL/SQL → Snowflake SQL", "migration",      "Amelia"),
    ("Generate validation rules",            "validation",     "Mary"),
    ("Build recon notebook",                 "notebook",       "Amelia"),
    ("Reconcile sample run",                 "recon",          None),
    ("Adversarial code review (migrate.py)", "code_review",    "Amelia"),
    ("Approve cutover plan",                 "qa",             None),
]

TASK_STATUSES = [
    "completed", "completed", "in_progress", "ai_processing",
    "human_review", "validation", "recon", "blocked",
]

AGENT_NAME_TO_CODE = {
    "Mary":    "bmad-agent-analyst",
    "John":    "bmad-agent-pm",
    "Sally":   "bmad-agent-ux-designer",
    "Winston": "bmad-agent-architect",
    "Amelia":  "bmad-agent-dev",
    "Paige":   "bmad-agent-tech-writer",
}


def _seed_clean(db: Session, org_id: str, project_id: str) -> None:
    """Wipe any prior sprint data for this project so re-seed is deterministic."""
    db.query(AgentExecutionRecord).filter(
        AgentExecutionRecord.organization_id == org_id,
        AgentExecutionRecord.project_id == project_id,
    ).delete(synchronize_session=False)
    db.query(MappingEdge).filter(
        MappingEdge.organization_id == org_id,
        MappingEdge.project_id == project_id,
    ).delete(synchronize_session=False)
    db.query(MappingNode).filter(
        MappingNode.organization_id == org_id,
        MappingNode.project_id == project_id,
    ).delete(synchronize_session=False)
    db.query(MigrationRelease).filter(
        MigrationRelease.organization_id == org_id,
        MigrationRelease.project_id == project_id,
    ).delete(synchronize_session=False)
    # Sprints + cascades cover tasks/risks/approvals.
    db.query(Sprint).filter(
        Sprint.organization_id == org_id,
        Sprint.project_id == project_id,
    ).delete(synchronize_session=False)
    db.commit()


def seed_sprints_for_project(db: Session, org_id: str, project_id: str) -> dict:
    """Populate the demo sprint dataset. Returns counts + duration."""
    start = time.time()
    _seed_clean(db, org_id, project_id)

    base = datetime(2026, 4, 6, tzinfo=timezone.utc)
    sprints: list[Sprint] = []
    for i, plan in enumerate(SPRINT_PLAN):
        s_start = base + timedelta(days=14 * i)
        s_end   = s_start + timedelta(days=13)
        total_sp = 60 + i * 5
        done_sp  = total_sp if plan["status"] == "completed" else (38 if i == 2 else 0)
        sp = Sprint(
            organization_id=org_id,
            project_id=project_id,
            index=i + 1,
            name=f"Sprint {i + 1} — {plan['name']}",
            goal=plan["goal"],
            status=plan["status"],
            health=plan["health"],
            start_date=s_start,
            end_date=s_end,
            metrics={
                "storyPointsTotal": total_sp,
                "storyPointsDone": done_sp,
                "tasksTotal": 24,
                "tasksDone": 24 if plan["status"] == "completed" else (15 if i == 2 else 0),
                "validationCoveragePct": 96 if plan["status"] == "completed" else (64 if i == 2 else 0),
                "reconCoveragePct":      98 if plan["status"] == "completed" else (58 if i == 2 else 0),
                "aiAutomationPct": 71,
                "humanApprovalsPending": 4 if i == 2 else 0,
                "openRisks": 3 if i == 2 else 0,
                "criticalIssues": 1 if i == 2 else 0,
                "velocity": 56 + i * 3,
            },
            milestones=[
                {"id": f"M{i+1}-1", "label": "Sprint kickoff",    "date": s_start.date().isoformat(),                "kind": "discovery",  "status": "done" if plan["status"] == "completed" else "done" if plan["status"] == "active" else "pending"},
                {"id": f"M{i+1}-2", "label": "Mid-sprint review", "date": (s_start + timedelta(days=7)).date().isoformat(), "kind": "mapping",   "status": "done" if plan["status"] == "completed" else "in_progress" if plan["status"] == "active" else "pending"},
                {"id": f"M{i+1}-3", "label": "Sprint demo",       "date": s_end.date().isoformat(),                  "kind": "validation","status": "done" if plan["status"] == "completed" else "pending"},
            ],
        )
        db.add(sp)
        sprints.append(sp)
    db.flush()  # populate sprint IDs

    active_sprint = next((s for s in sprints if s.status == "active"), sprints[0])

    # ── Tasks (24 = 8 templates × 3 schemas) for active sprint ────
    schemas = ["GL_LEDGER", "GL_TRANS", "GL_RECON"]
    tasks: list[SprintTask] = []
    for idx, (title, ttype, agent) in enumerate(TASK_TEMPLATES):
        for s_i, schema in enumerate(schemas):
            status = TASK_STATUSES[(idx + s_i) % len(TASK_STATUSES)]
            sp_count = [1, 2, 3, 5, 8][idx % 5]
            t = SprintTask(
                organization_id=org_id,
                sprint_id=active_sprint.id,
                title=f"{title} ({schema})",
                type=ttype,
                status=status,
                priority=["P0", "P1", "P2", "P3"][idx % 4],
                owner_name=agent or ["Priya Shah", "Daniel Park", "Mei Lin", "Tomás Ribeiro", "Avery Johnson"][idx % 5],
                owner_kind="agent" if agent else "human",
                ai_agent=AGENT_NAME_TO_CODE.get(agent or "") if agent else None,
                epic_id=f"{active_sprint.id}-E{(idx % 3) + 1}",
                risk_level="critical" if idx == 7 else "high" if idx % 4 == 0 else "med" if idx % 2 == 0 else "low",
                story_points=sp_count,
                estimated_hours=8 + idx,
                actual_hours=(7 + idx) if status == "completed" else None,
                validation_status=["pass", "warn", "pending", "fail"][idx % 4],
                recon_status=["pending", "pass", "warn", "pending"][idx % 4],
                dependency_ids=[],
                artifact_ids=[f"art-{idx}", f"art-{idx}-spec"],
                blocked_reason="Awaiting target Snowflake warehouse provisioning" if status == "blocked" else None,
            )
            db.add(t)
            tasks.append(t)

    # ── Risks (active sprint) ───────────────────────────────────────
    risks = [
        SprintRisk(organization_id=org_id, sprint_id=active_sprint.id, title="Validation coverage trending below threshold", category="validation", level="high",     description="GL_TRANS validations are flaky on null timestamps — 6/47 rules failing.", mitigation="Tighten coalesce + add fallback to source createdAt.", status="mitigating", ai_confidence=71),
        SprintRisk(organization_id=org_id, sprint_id=active_sprint.id, title="Snowflake warehouse provisioning delay",       category="deployment", level="critical", description="Procurement has not signed off on the X-LARGE SKU for prod recon runs.", mitigation="Run with LARGE + extend recon window by 2h.",         status="open"),
        SprintRisk(organization_id=org_id, sprint_id=active_sprint.id, title="PII column not classified in source",          category="compliance", level="med",      description="customer_email_alt found unclassified in GL_AUDIT.",                       mitigation="Run profiler with regex pack; tag + mask.",           status="mitigating", ai_confidence=88),
    ]
    for r in risks:
        db.add(r)

    # ── Approvals (active sprint) ───────────────────────────────────
    approvals = [
        SprintApproval(organization_id=org_id, sprint_id=active_sprint.id, kind="milestone",           title="Approve mid-sprint review",            requested_by="Priya Shah", approvers=["Avery Johnson"]),
        SprintApproval(organization_id=org_id, sprint_id=active_sprint.id, kind="code_review",         title="Adversarial review for migrate.py",   requested_by="Amelia",     approvers=["Mei Lin"]),
        SprintApproval(organization_id=org_id, sprint_id=active_sprint.id, kind="release",             title="Release 2026.05.27 go/no-go",          requested_by="Priya Shah", approvers=["Avery Johnson", "Daniel Park"]),
        SprintApproval(organization_id=org_id, sprint_id=active_sprint.id, kind="validation_override", title="Override 3 minor validation warnings", requested_by="Mei Lin",    approvers=["Avery Johnson"]),
    ]
    for a in approvals:
        db.add(a)

    # ── Releases ────────────────────────────────────────────────────
    releases = [
        MigrationRelease(
            organization_id=org_id, project_id=project_id,
            name="Release 2026.05.27 — GL Core Cutover",
            sprint_ids=[s.id for s in sprints[2:4]],
            stage="validation",
            target_environment="prod",
            scheduled_for=datetime(2026, 5, 27, 18, 0, tzinfo=timezone.utc),
            validation_score=64, recon_score=58, rollback_ready=True,
            checklist=[
                {"id": "c1", "label": "All P0 tasks completed",      "done": True,  "owner": "Priya Shah"},
                {"id": "c2", "label": "Validation ≥ 95%",            "done": False, "owner": "Mei Lin"},
                {"id": "c3", "label": "Recon parity ≥ 99%",          "done": False, "owner": "Tomás Ribeiro"},
                {"id": "c4", "label": "Rollback playbook sign-off",  "done": True,  "owner": "Avery Johnson"},
                {"id": "c5", "label": "DBA on-call confirmed",       "done": False, "owner": "Daniel Park"},
                {"id": "c6", "label": "Stakeholder go/no-go meeting", "done": False, "owner": "Priya Shah"},
            ],
        ),
        MigrationRelease(
            organization_id=org_id, project_id=project_id,
            name="Release 2026.06.10 — Reporting Layer",
            sprint_ids=[sprints[4].id],
            stage="planned",
            target_environment="staging",
            scheduled_for=datetime(2026, 6, 10, 18, 0, tzinfo=timezone.utc),
            validation_score=0, recon_score=0, rollback_ready=False,
            checklist=[],
        ),
    ]
    for rel in releases:
        db.add(rel)

    # ── Mapping canvas ──────────────────────────────────────────────
    node_specs = [
        ("n1",  "requirement_intake",  "Requirement Intake",  "Mary",    "completed",     100, None,  12, "approved",   1,  40,   240),
        ("n2",  "source_discovery",    "Source Discovery",    "Mary",    "completed",      96, None,  18, "approved",   4, 240,   120),
        ("n3",  "schema_mapping",      "Schema Mapping",      "Winston", "completed",      92, None,  22, "approved",   7, 240,   360),
        ("n4",  "etl_conversion",      "ETL Conversion",      "Amelia",  "ai_processing", None, None, 48, "not_required", 12, 460, 240),
        ("n5",  "notebook_generation", "Notebook Generation", "Amelia",  "active",        None, None, 34, "not_required",  5, 680, 120),
        ("n6",  "validation",          "Validation",          "Mary",    "review",          64, None, 56, "pending",       8, 680, 360),
        ("n7",  "recon",               "Reconciliation",      None,      "pending",       None, None, 41, "pending",       0, 900, 240),
        ("n8",  "qa",                  "QA Sign-off",         "Amelia",  "pending",       None, None, 30, "pending",       0,1120, 120),
        ("n9",  "uat",                 "UAT",                 None,      "pending",       None, None, 28, "pending",       0,1120, 360),
        ("n10", "production_approval", "Production Approval", None,      "pending",       None, None, 24, "pending",       0,1340, 240),
        ("n11", "release_deployment",  "Release Deployment",  None,      "pending",       None, None, 22, "pending",       0,1560, 240),
    ]
    node_objs: dict[str, MappingNode] = {}
    for key, kind, label, agent_name, status, val, rec, risk, approval, art, x, y in node_specs:
        n = MappingNode(
            organization_id=org_id, project_id=project_id,
            kind=kind, label=label,
            agent=AGENT_NAME_TO_CODE.get(agent_name or "") if agent_name else None,
            status=status,
            validation_score=val, recon_score=rec, risk_score=risk,
            approval_status=approval, artifact_count=art,
            position_x=float(x), position_y=float(y),
        )
        db.add(n)
        node_objs[key] = n
    db.flush()

    edge_specs = [
        ("n1", "n2",  "completed", None),
        ("n1", "n3",  "completed", None),
        ("n2", "n4",  "completed", None),
        ("n3", "n4",  "completed", None),
        ("n4", "n5",  "active",    None),
        ("n4", "n6",  "active",    None),
        ("n5", "n7",  "pending",   None),
        ("n6", "n7",  "blocked",   "validation < 80%"),
        ("n7", "n8",  "pending",   None),
        ("n7", "n9",  "pending",   None),
        ("n8", "n10", "pending",   None),
        ("n9", "n10", "pending",   None),
        ("n10", "n11", "pending",  None),
    ]
    edges = 0
    for s_key, t_key, status, label in edge_specs:
        db.add(MappingEdge(
            organization_id=org_id, project_id=project_id,
            source_id=node_objs[s_key].id, target_id=node_objs[t_key].id,
            status=status, label=label,
        ))
        edges += 1

    # ── Agent executions ────────────────────────────────────────────
    now = datetime.now(timezone.utc)
    executions = [
        AgentExecutionRecord(organization_id=org_id, project_id=project_id, agent_code="bmad-agent-dev",         status="running",   started_at=now - timedelta(minutes=6),  retries=0, mode="llm",  log="Generating MERGE statement for GL_TRANS … phase 3/5"),
        AgentExecutionRecord(organization_id=org_id, project_id=project_id, agent_code="bmad-agent-analyst",     status="succeeded", started_at=now - timedelta(minutes=22), duration_ms=184_000, retries=0, mode="llm",  log="Profiled 412 columns, 17 anomalies flagged"),
        AgentExecutionRecord(organization_id=org_id, project_id=project_id, agent_code="bmad-agent-architect",   status="succeeded", started_at=now - timedelta(minutes=49), duration_ms=92_000,  retries=0, mode="llm",  log="Mapped trans_fact with 4 type coercions"),
        AgentExecutionRecord(organization_id=org_id, project_id=project_id, agent_code="bmad-agent-dev",         status="retrying",  started_at=now - timedelta(minutes=18), retries=2, mode="llm",  log="Notebook gen failed — retry 2/3 with smaller context"),
        AgentExecutionRecord(organization_id=org_id, project_id=project_id, agent_code="bmad-agent-dev",         status="queued",    started_at=now,                          retries=0, mode="mock", log="Awaiting upstream code-review artifact"),
        AgentExecutionRecord(organization_id=org_id, project_id=project_id, agent_code="bmad-agent-tech-writer", status="failed",    started_at=now - timedelta(hours=2),    duration_ms=41_000,  retries=3, mode="llm",  log="Rate-limited by Anthropic after 3 retries"),
    ]
    for ex in executions:
        db.add(ex)

    db.commit()

    return {
        "project_id": project_id,
        "sprints_created": len(sprints),
        "tasks_created": len(tasks),
        "risks_created": len(risks),
        "approvals_created": len(approvals),
        "releases_created": len(releases),
        "mapping_nodes_created": len(node_specs),
        "mapping_edges_created": edges,
        "executions_created": len(executions),
        "duration_ms": int((time.time() - start) * 1000),
    }
