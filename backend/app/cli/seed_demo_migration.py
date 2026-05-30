"""Seed a realistic, ALREADY-COMPLETED DB-migration into Postgres.

Lets the Helix demo show a full, production-looking migration (schema analysis,
type mapping, DDL/data/rollback SQL, reconciliation report) served by the real
APIs from the DB — with NO LLM calls and no live source/target DB.

Run:  docker exec helix-backend python -m app.cli.seed_demo_migration
Defaults to the first organization + that org's first user as owner.
Idempotent: re-running replaces the prior "DEMO — Oracle HR → Snowflake" project.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from uuid import uuid4

from app.db.session import SessionLocal
from app.models.identity import Organization, User
from app.models.project import (
    MigrationRequirement,
    Project,
    SourceConnection,
    TargetConnection,
)
from app.models.schema_snapshot import SourceSchemaSnapshot
from app.models.validation import ReconResult, ReconRun
from app.models.workflow import WorkflowRun, WorkflowStep
from app.services.workflow_service import create_workflow_run

# NOTE: connections are created as rows directly (not via project_service.add_*)
# so this seeder has NO fastapi dependency and can run inside the WORKER
# container — which holds the artifact volume read-WRITE (the backend mounts it
# read-only). The demo configs are placeholders; the connection is never dialed.

PROJECT_NAME = "DEMO — Oracle HR → Snowflake"

# ── The classic Oracle HR schema (7 tables) + approximate row counts ──────────
_HR_TABLES = [
    ("REGIONS", 4, [("REGION_ID", "NUMBER", False), ("REGION_NAME", "VARCHAR2(25)", True)]),
    ("COUNTRIES", 25, [("COUNTRY_ID", "CHAR(2)", False), ("COUNTRY_NAME", "VARCHAR2(40)", True), ("REGION_ID", "NUMBER", True)]),
    ("LOCATIONS", 23, [("LOCATION_ID", "NUMBER(4)", False), ("STREET_ADDRESS", "VARCHAR2(40)", True), ("POSTAL_CODE", "VARCHAR2(12)", True), ("CITY", "VARCHAR2(30)", False), ("STATE_PROVINCE", "VARCHAR2(25)", True), ("COUNTRY_ID", "CHAR(2)", True)]),
    ("DEPARTMENTS", 27, [("DEPARTMENT_ID", "NUMBER(4)", False), ("DEPARTMENT_NAME", "VARCHAR2(30)", False), ("MANAGER_ID", "NUMBER(6)", True), ("LOCATION_ID", "NUMBER(4)", True)]),
    ("JOBS", 19, [("JOB_ID", "VARCHAR2(10)", False), ("JOB_TITLE", "VARCHAR2(35)", False), ("MIN_SALARY", "NUMBER(6)", True), ("MAX_SALARY", "NUMBER(6)", True)]),
    ("EMPLOYEES", 107, [("EMPLOYEE_ID", "NUMBER(6)", False), ("FIRST_NAME", "VARCHAR2(20)", True), ("LAST_NAME", "VARCHAR2(25)", False), ("EMAIL", "VARCHAR2(25)", False), ("PHONE_NUMBER", "VARCHAR2(20)", True), ("HIRE_DATE", "DATE", False), ("JOB_ID", "VARCHAR2(10)", False), ("SALARY", "NUMBER(8,2)", True), ("COMMISSION_PCT", "NUMBER(2,2)", True), ("MANAGER_ID", "NUMBER(6)", True), ("DEPARTMENT_ID", "NUMBER(4)", True)]),
    ("JOB_HISTORY", 10, [("EMPLOYEE_ID", "NUMBER(6)", False), ("START_DATE", "DATE", False), ("END_DATE", "DATE", False), ("JOB_ID", "VARCHAR2(10)", False), ("DEPARTMENT_ID", "NUMBER(4)", True)]),
]
# JOB_HISTORY target lands 9 of 10 rows → the one demo mismatch.
_TARGET_ROWS = {"REGIONS": 4, "COUNTRIES": 25, "LOCATIONS": 23, "DEPARTMENTS": 27, "JOBS": 19, "EMPLOYEES": 107, "JOB_HISTORY": 9}

# Oracle → Snowflake type mapping rules.
_TYPE_MAP = [
    ("VARCHAR2(n)", "VARCHAR(n)", "Direct; Snowflake VARCHAR length is a max, not a fixed width."),
    ("CHAR(n)", "CHAR(n)", "Direct."),
    ("NUMBER(p,s)", "NUMBER(p,s)", "Direct; precision/scale preserved."),
    ("NUMBER (unscaled)", "NUMBER(38,0)", "Oracle unscaled NUMBER → max precision integer."),
    ("DATE", "TIMESTAMP_NTZ", "Oracle DATE carries a time component; TIMESTAMP_NTZ avoids truncation."),
    ("CLOB", "VARCHAR", "Snowflake VARCHAR holds up to 16 MB; no separate LOB type."),
]


def _schema_model() -> dict:
    schemas = [{
        "schema": "HR",
        "tables": [
            {"table": t, "row_count": rc, "columns": [{"name": c, "type": ty, "nullable": n} for (c, ty, n) in cols]}
            for (t, rc, cols) in _HR_TABLES
        ],
    }]
    tcount = len(_HR_TABLES)
    ccount = sum(len(cols) for (_, _, cols) in _HR_TABLES)
    return {"source_connector_type": "oracle", "schemas": schemas, "table_count": tcount, "column_count": ccount, "truncated": False}


# ── Snowflake type translation (deterministic, mirrors _TYPE_MAP) ─────────────
def _to_snowflake(oracle_type: str) -> str:
    t = oracle_type.upper()
    if t.startswith("VARCHAR2"):
        return "VARCHAR" + t[len("VARCHAR2"):]
    if t.startswith("CHAR"):
        return t
    if t == "DATE":
        return "TIMESTAMP_NTZ"
    if t == "CLOB":
        return "VARCHAR"
    if t.startswith("NUMBER"):
        return t if "(" in t else "NUMBER(38,0)"
    return t


def _ddl_body(model: dict) -> str:
    lines = ["# Target DDL — Snowflake (ANALYTICS.HR)\n", "```sql"]
    for sb in model["schemas"]:
        for tbl in sb["tables"]:
            lines.append(f"CREATE TABLE IF NOT EXISTS ANALYTICS.HR.{tbl['table']} (")
            cols = []
            for c in tbl["columns"]:
                null = "" if c["nullable"] else " NOT NULL"
                cols.append(f"    {c['name']} {_to_snowflake(c['type'])}{null}")
            lines.append(",\n".join(cols))
            lines.append(");")
            lines.append("")
    lines.append("-- Primary keys")
    lines.append("ALTER TABLE ANALYTICS.HR.EMPLOYEES   ADD PRIMARY KEY (EMPLOYEE_ID);")
    lines.append("ALTER TABLE ANALYTICS.HR.DEPARTMENTS ADD PRIMARY KEY (DEPARTMENT_ID);")
    lines.append("ALTER TABLE ANALYTICS.HR.JOBS        ADD PRIMARY KEY (JOB_ID);")
    lines.append("```")
    return "\n".join(lines)


def _data_body(model: dict) -> str:
    lines = ["# Data Migration — Oracle → Snowflake\n",
             "Bulk load via staged Parquet for large tables; INSERT...SELECT shown for clarity.\n", "```sql"]
    for sb in model["schemas"]:
        for tbl in sb["tables"]:
            collist = ", ".join(c["name"] for c in tbl["columns"])
            lines.append(f"-- {tbl['table']} (~{tbl['row_count']} rows)")
            lines.append(f"INSERT INTO ANALYTICS.HR.{tbl['table']} ({collist})")
            lines.append(f"SELECT {collist} FROM staged.hr_{tbl['table'].lower()};")
            lines.append("")
    lines.append("```")
    return "\n".join(lines)


def _rollback_body(model: dict) -> str:
    order = [t["table"] for sb in model["schemas"] for t in sb["tables"]]
    lines = ["# Rollback — drop target tables in reverse dependency order\n", "```sql"]
    for t in reversed(order):
        lines.append(f"DROP TABLE IF EXISTS ANALYTICS.HR.{t};")
    lines.append("```")
    return "\n".join(lines)


def _mapping_body() -> str:
    rows = "\n".join(f"| `{o}` | `{s}` | {note} |" for (o, s, note) in _TYPE_MAP)
    return (
        "# Type Mapping — Oracle → Snowflake\n\n"
        "| Oracle | Snowflake | Note |\n|---|---|---|\n" + rows + "\n\n"
        "## Ambiguous / needs review\n"
        "- **EMPLOYEES.HIRE_DATE** `DATE → TIMESTAMP_NTZ` — Oracle `DATE` includes a time "
        "component; mapping to `TIMESTAMP_NTZ` preserves it (use `DATE` only if time is known to be 00:00:00).\n"
        "- **Unscaled `NUMBER` columns** → `NUMBER(38,0)` — confirm none exceed 38 digits.\n"
    )


def _recon_body() -> str:
    lines = ["# Reconciliation Report\n", "**Verified: 98.7%** (row-count parity, 7 tables)\n",
             "| Table | Source | Target | Match |\n|---|---:|---:|:--:|"]
    for (t, rc, _cols) in _HR_TABLES:
        tgt = _TARGET_ROWS[t]
        lines.append(f"| {t} | {rc} | {tgt} | {'✅' if tgt == rc else '⚠️'} |")
    lines.append("\n> **JOB_HISTORY**: 1 source row failed the target NOT NULL on `END_DATE` "
                 "(an open assignment with no end date). Resolve by allowing NULL `END_DATE` on the "
                 "target or backfilling, then re-run reconciliation.")
    return "\n".join(lines)


def seed_demo_migration(org_id: str | None = None, owner_id: str | None = None) -> str:
    from agents.runtime.artifact_store import write_artifact

    db = SessionLocal()
    try:
        if org_id is None:
            org = db.query(Organization).order_by(Organization.created_at.asc()).first()
            if not org:
                raise RuntimeError("No organization found — create the first admin first.")
            org_id = org.id
        if owner_id is None:
            user = db.query(User).order_by(User.created_at.asc()).first()
            owner_id = user.id if user else org_id

        # ── Idempotent teardown of a prior demo project ──────────────────────
        for proj in db.query(Project).filter(Project.organization_id == org_id, Project.name == PROJECT_NAME).all():
            pid = proj.id
            for rr in db.query(ReconRun).filter(ReconRun.project_id == pid).all():
                db.query(ReconResult).filter(ReconResult.run_id == rr.id).delete()
                db.delete(rr)
            for wf in db.query(WorkflowRun).filter(WorkflowRun.project_id == pid).all():
                db.query(WorkflowStep).filter(WorkflowStep.workflow_run_id == wf.id).delete()
                db.delete(wf)
            db.query(SourceSchemaSnapshot).filter(SourceSchemaSnapshot.project_id == pid).delete()
            db.query(MigrationRequirement).filter(MigrationRequirement.project_id == pid).delete()
            db.query(SourceConnection).filter(SourceConnection.project_id == pid).delete()
            db.query(TargetConnection).filter(TargetConnection.project_id == pid).delete()
            db.delete(proj)
        db.commit()

        # ── Project + connections + requirement ──────────────────────────────
        proj = Project(
            organization_id=org_id, name=PROJECT_NAME, owner_id=owner_id, status="active",
            risk_level="medium", migration_type="oracle-to-snowflake",
            description="Demo: migrate the Oracle HR schema (7 tables) to Snowflake with row-level reconciliation.",
        )
        db.add(proj)
        db.commit()
        db.refresh(proj)
        pid = proj.id

        db.add(SourceConnection(
            organization_id=org_id, project_id=pid, name="HR Oracle (demo)",
            connector_type="oracle", status="active",
            config_masked="host=oracle-hr.demo.internal:1521 service=ORCLPDB1 user=hr password=••••",
        ))
        db.add(TargetConnection(
            organization_id=org_id, project_id=pid, name="Analytics Snowflake (demo)",
            connector_type="snowflake", status="active",
            config_masked="account=acme-eu.west1 db=ANALYTICS wh=HELIX_WH role=HELIX_ROLE user=helix",
        ))
        db.flush()

        req = MigrationRequirement(
            project_id=pid, status="approved",
            source_text="Migrate the Oracle HR schema (7 tables) to Snowflake with row-level reconciliation.",
        )
        db.add(req)
        db.commit()
        db.refresh(req)

        # ── Completed workflow run ───────────────────────────────────────────
        run_uuid = str(uuid4())
        wid = f"mig-{pid}-{req.id}"
        create_workflow_run(
            db, organization_id=org_id, project_id=pid, requirement_id=req.id,
            workflow_id=wid, run_id="demo-seed", status="completed", mode="temporal",
            run_uuid=run_uuid, kind="migration",
        )

        model = _schema_model()
        # ── Artifacts ────────────────────────────────────────────────────────
        art_schema = write_artifact(project_id=pid, agent_code="schema_analyst", skill="migration-analyze-schema",
                                    filename="analyzed-source-schema", phase="analysis",
                                    body="# Analyzed Source Schema (Oracle HR)\n\n```json\n" + json.dumps(model, indent=2) + "\n```\n")
        art_map = write_artifact(project_id=pid, agent_code="type_mapper", skill="migration-map-types",
                                 filename="type-mapping", phase="planning", body=_mapping_body())
        art_ddl = write_artifact(project_id=pid, agent_code="script_generator", skill="migration-generate-scripts",
                                 filename="target-ddl", phase="implementation", body=_ddl_body(model))
        write_artifact(project_id=pid, agent_code="script_generator", skill="migration-generate-scripts",
                       filename="data-migration", phase="implementation", body=_data_body(model))
        write_artifact(project_id=pid, agent_code="script_generator", skill="migration-generate-scripts",
                       filename="rollback", phase="implementation", body=_rollback_body(model))
        art_recon = write_artifact(project_id=pid, agent_code="reconciler", skill="migration-reconcile",
                                   filename="reconciliation-report", phase="implementation", body=_recon_body())

        # ── Steps ────────────────────────────────────────────────────────────
        steps = [
            ("schema_analyst", 1, None, None, str(art_schema.path),
             {"summary": "Introspected HR schema: 7 tables, 51 columns", "schema_count": 1, "table_count": 7, "column_count": 51, "truncated": False}),
            ("type_mapper", 2, "deepseek", "deepseek-chat", str(art_map.path),
             {"summary": "Mapped 7 tables to Snowflake; 2 ambiguous", "mapping_count": 18, "approval_required": True,
              "ambiguous_mappings": [
                  {"table": "EMPLOYEES", "column": "HIRE_DATE", "source_type": "DATE", "target_type": "TIMESTAMP_NTZ", "reason": "Oracle DATE carries a time component"},
                  {"table": "EMPLOYEES", "column": "SALARY", "source_type": "NUMBER(8,2)", "target_type": "NUMBER(8,2)", "reason": "ok"}],
              "truncated": False}),
            ("script_generator", 3, "deepseek", "deepseek-chat", str(art_ddl.path),
             {"summary": "Generated Snowflake DDL + data-migration + rollback for 7 tables", "execution_enabled": False,
              "tables_scripted": 7, "manual_steps": ["Create ANALYTICS.HR schema + HELIX_WH before running", "Use COPY from staged Parquet for tables > 1M rows"], "truncated": False}),
            ("reconciler", 4, None, None, str(art_recon.path),
             {"summary": "Row-count reconciliation across 7 tables", "verified_pct": 98.7, "tables_checked": 7, "matched": 6, "mismatched": 1, "errors_count": 0}),
        ]
        for agent_name, order, prov, mdl, apath, parsed in steps:
            db.add(WorkflowStep(
                workflow_run_id=run_uuid, agent_name=agent_name, step_order=order, status="completed",
                raw_output=json.dumps({**parsed, "artifact_path": apath}), parsed_output_json=parsed,
                provider_name=prov, model_name=mdl, error_message=None,
            ))

        # ── Source schema snapshot ───────────────────────────────────────────
        db.add(SourceSchemaSnapshot(
            organization_id=org_id, project_id=pid, source_ref="oracle", payload=json.dumps(model),
            table_count=model["table_count"], column_count=model["column_count"],
            taken_at=datetime.now(timezone.utc), notes="demo seed",
        ))

        # ── Reconciliation run + results ─────────────────────────────────────
        recon = ReconRun(project_id=pid, source_ref="oracle", target_ref="snowflake", status="completed")
        db.add(recon)
        db.flush()
        for (t, rc, _cols) in _HR_TABLES:
            tgt = _TARGET_ROWS[t]
            db.add(ReconResult(
                run_id=recon.id, result_type="row_count",
                summary=f"HR.{t}: source={rc} target={tgt}",
                mismatch_count=abs(rc - tgt), details_ref=None,
            ))

        db.commit()
        return pid
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    org = sys.argv[1] if len(sys.argv) > 1 else None
    owner = sys.argv[2] if len(sys.argv) > 2 else None
    pid = seed_demo_migration(org, owner)
    print(f"SEEDED demo migration project: {pid}")
    print(f"Open: /projects/{pid}/migration")


if __name__ == "__main__":
    main()
