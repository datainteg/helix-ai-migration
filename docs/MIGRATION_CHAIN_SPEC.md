# BUILD SPEC — DB-Migration Agent Chain (SchemaAnalyst → TypeMapper → ScriptGenerator → Reconciler)

**Status:** Design / build-ready. No code in this doc.
**Author:** Lead engineer
**Coexists with:** the existing BMAD planning pipeline (13-node per-node Temporal workflow).
**Guiding principle:** clone the proven per-node Temporal scaffold (`worker/workflows/bmad_per_node_workflow.py`); add a *second* `@workflow.defn` type on the *same* worker and *same* task queue; reuse `WorkflowRun`/`WorkflowStep` persistence, the approval gate, the SSE stream, and the artifact store **unchanged**. The migration chain is 4 nodes vs BMAD's 13 and has the same single-gate shape, so the delta is purely additive.

All file paths below are absolute under the repo root `/home/akshay/projects`.

---

## 1. Architecture Overview

The migration chain is a new Temporal workflow type registered next to the two BMAD workflow types. Temporal dispatches by `(task_queue, workflow_type_name)`, so adding a third type to the same worker on the same queue is non-regressive: a client starting `BMADPerNodeWorkflow.run` is never routed to `MigrationPerNodeWorkflow` and vice-versa.

Two of the four nodes are **deterministic** (no LLM): SchemaAnalyst (introspection via the connector layer) and Reconciler (row-count + schema-compare via `recon_service`/`validation_service`). Two are **LLM** nodes reusing the existing `execute_agent_skill` transport stack: TypeMapper and ScriptGenerator. The human approval gate sits **after TypeMapper** so a reviewer signs off the proposed type mapping (lossy/ambiguous cases) before any DDL or data-migration SQL is generated.

Confirmed against code:
- Worker registers `workflows=[BMADPlanningWorkflow, BMADPerNodeWorkflow]` on `TASK_QUEUE` (default `helix-bmad-task-queue`) — `worker/main.py:56,157`.
- `persist_workflow_step_activity` / `persist_workflow_terminal_state_activity` are agent-name agnostic (key on `workflow_run_id`/`step_order`/`workflow_id`) — `worker/activities/bmad_node_activities.py:414,467`.
- The run-id contract is intact: `create_workflow_run(..., run_uuid=helix.workflow_run_id)` pins `WorkflowRun.id` to the UUID the worker stamps onto every step — `backend/app/services/workflow_service.py:391-392`, `worker/workflows/bmad_per_node_workflow.py:132,176`.
- SSE `done` terminal set is `("completed","approved","rejected","failed")` — `backend/app/api/agent_workflows.py:466` (**note: `expired` is NOT in it**; design decision in §6).
- `SAFE_EXECUTION_MODE = "analysis_only"` declared at `backend/app/core/config.py:65`, **consumed nowhere today** (verified). This spec makes it the single execution kill-switch.
- Alembic head is `v3w4x5y6z7a8` (`backend/alembic/versions/v3w4x5y6z7a8_fix_validation_recon_nullability.py`) → new migration's `down_revision`.

### ASCII diagram — both chains on one worker / one queue

```
                         ┌──────────────────────────────────────────────────────┐
   Backend (FastAPI)     │  Temporal server  (TEMPORAL_ADDRESS, localhost:7233)   │
                         │                                                        │
 POST /projects/{id}/    │   task_queue = "helix-bmad-task-queue"                 │
   agent-workflows ──────┼──► workflow_type = BMADPerNodeWorkflow   (13 nodes)    │
   (start_bmad_*)        │                                                        │
                         │                                                        │
 POST /projects/{id}/    │                                                        │
   migrations    ────────┼──► workflow_type = MigrationPerNodeWorkflow (4 nodes)  │  ◄── NEW
   (start_migration_*)   │       id = "mig-{project}-{requirement}"               │
                         └───────────────────────┬────────────────────────────────┘
                                                 │ both dispatched to
                                                 ▼
            ┌──────────────────────────────────────────────────────────────────┐
            │   SINGLE Worker process  (worker/main.py)                          │
            │   ThreadPoolExecutor(max=WORKER_MAX_CONCURRENT_ACTIVITIES)         │
            │                                                                    │
            │   workflows = [ BMADPlanningWorkflow,                              │
            │                 BMADPerNodeWorkflow,                               │
            │                 MigrationPerNodeWorkflow ]      ◄── add 1          │
            │                                                                    │
            │   activities = [ ...15 BMAD activities...,                         │
            │                  schema_analyst_activity,        ◄── add 4         │
            │                  type_mapper_activity,                             │
            │                  script_generator_activity,                        │
            │                  reconciler_activity,                              │
            │                  persist_workflow_step_activity,    (reused)       │
            │                  persist_workflow_terminal_state_activity ]        │
            └──────────────────────────────────────────────────────────────────┘

  MigrationPerNodeWorkflow.run sequence:
     step1 SchemaAnalyst (deterministic) ─► step2 TypeMapper (LLM)
        ─► [APPROVAL GATE: workflow.wait_condition on approve/reject, 48h]
        ─► step3 ScriptGenerator (LLM+templates) ─► step4 Reconciler (deterministic)
     every exit path ─► persist_workflow_terminal_state_activity (reused)

  Shared persistence (NO schema change to step rows):
     workflow_runs  (+ new nullable `kind` col)   workflow_steps  (unchanged)
     recon_runs / recon_results (reused)           source_schema_snapshots (reused)
```

---

## 2. The Four Nodes — responsibility, IO contract, artifacts, LLM-vs-deterministic

Each activity returns the **same dict shape** the BMAD activities return so the reused `run_step()` + `persist_workflow_step_activity` work verbatim:
`{ "agent": str, "skill": str, "success": bool, "mode": str, "errors": list[str], "artifact_path": str|None, "parsed": dict|None }` — matches `worker/activities/bmad_node_activities.py:118-126`.

`input_data` (the workflow payload, built by `HelixMigration._input_payload()`) carries:
`project_id, requirement_id, organization_id, requirement_text, workflow_run_id, correlation_id` (existing keys) **plus** `source_connection_id, target_connection_id, source_connector_type, target_connector_type, source_config, target_config, in_scope_schemas` (new keys). Decrypted configs are resolved at the HTTP boundary — see §3.5 (the worker cannot decrypt).

### Node 1 — SchemaAnalyst (DETERMINISTIC, step_order=1)
- **Responsibility:** introspect the project SOURCE connector into a normalized, dialect-tagged schema model. No LLM.
- **Inputs:** `source_connector_type` + `source_config` from `input_data`; calls `connector_service.discover_schemas/discover_tables/discover_columns/get_row_count` (`backend/app/services/connector_service.py:56-73`). **The activity owns the fan-out**: `list_schemas → for each in-scope schema list_tables → for each table list_columns + get_row_count` (the discovery endpoints return one table's columns per call — verified at `connector_service.py:66`).
- **Why a sync `def` activity calling connectors directly (not `execute_agent_skill`):** deterministic. Run it inside `_run_with_heartbeats` (`bmad_node_activities.py:157`) because fan-out over a large DB can exceed the 60s heartbeat timeout. Connector classes are import-safe worker-side (`connectors.*`); `connector_service` itself is backend-only, so the activity either imports `connectors.base` + the connector class directly or re-implements the thin 3-call fan-out. Prefer importing the connector class via the same `_build_connector` shape (copy the 6-line factory into the worker to avoid pulling backend services).
- **Outputs / artifacts:**
  1. `analyzed-source-schema.json` written via `artifact_store.write_artifact(project_id, agent_code="migration-agent-schema-analyst", skill="migration-analyze-schema", filename="analyzed-source-schema", body=<json-in-fenced-block>, phase="migration")`. NOTE: `write_artifact` always slugs to a **`.md`** file (`artifact_store.py:258`) and `list_artifacts` globs `*.md` only — wrap the JSON in a fenced ```json block inside the `.md` body (do not write a bare `.json`).
  2. A `SourceSchemaSnapshot` row (`backend/app/models/schema_snapshot.py:14`) with `source_ref="src:<conn>"`, `payload=<json>` so the existing drift endpoints (`backend/app/api/schema_drift.py`) and `SchemaDriftCard` can render it later.
- **JSON contract per column (target shape):** `{schema, table, name, raw_type, nullable, ordinal, precision, scale, default, is_pk, is_fk, fk_target, is_unique, identity_or_sequence, check_constraints, comment}`.
- **CRITICAL GAP (must design around):** `ColumnInfo` (`connectors/base/connector.py:79-86`) carries only `schema_name, table_name, column_name, data_type, is_nullable, ordinal_position`. There is NO precision/scale/default/PK/FK/unique/check/sequence/identity/index/comment. The postgres connector reads `information_schema.columns` but **discards** `numeric_precision/numeric_scale/column_default` (per study; mirror the same for other connectors). **v1 stance:** SchemaAnalyst populates what it can and marks every absent field as `null`; downstream TypeMapper MUST set `requires_review=true` for any mapping that depends on a null precision/constraint. A2-3/A2-4 (§7) deepen introspection.

### Node 2 — TypeMapper (LLM, step_order=2)
- **Responsibility:** map every source type to a target-dialect equivalent; flag ambiguous/lossy mappings for the human gate.
- **Inputs:** `analyzed-source-schema.json` (read via `collect_prior_context` with `upstream_agents=["migration-agent-schema-analyst"]` — `artifact_store.py` collect path) + `target_connector_type` (so the LLM knows the destination dialect).
- **Mechanics:** thin sync `def` activity wrapping `_execute(agent_code="migration-agent-type-mapper", skill_name="migration-map-types", output_model_name="TypeMapperOutput", input_data, upstream_agents=["migration-agent-schema-analyst"], artifact_filename="type-mapping")` — mirrors `mary_analyze_activity` (`bmad_node_activities.py:219`). `execute_agent_skill` resolves the output model by name via `getattr(bmad_schemas, "TypeMapperOutput")` (`bmad_node_activities.py:99-102`) and writes the markdown+frontmatter artifact, returning `result.parsed.model_dump()`.
- **Outputs / artifacts:** `type-mapping.md` (human-readable body the reviewer reads at the gate) with frontmatter parsed into `TypeMapperOutput` (new schema, §3.2). `approval_required=true` whenever ANY mapping is lossy/ambiguous.
- **Mapping rules the SKILL.md must encode (deterministic anchors so the LLM only reasons about residuals):** Oracle `NUMBER(p,s)`→PG `NUMERIC(p,s)`; `NUMBER` (no precision)→ambiguous (flag); Oracle `DATE`→PG `TIMESTAMP` (lossy if mapped to `DATE`, flag); `TIMESTAMP WITH TIME ZONE`→`TIMESTAMPTZ`; `VARCHAR2(n CHAR/BYTE)`→`VARCHAR(n)` (byte-vs-char, flag); `CLOB`→`TEXT`, `BLOB`→`BYTEA`/Snowflake `BINARY`; `RAW`→`BYTEA`; Oracle sequences/`NEXTVAL` defaults→PG `IDENTITY`/`SEQUENCE`; `ROWID/UROWID`→no equivalent (flag); empty-string-is-NULL semantics (flag); triggers + PL/SQL packages/procedures→**no automatic translation in v1**, always `requires_review=true`. Snowflake target: `NUMBER(38,0)` default, `TIMESTAMP_NTZ` vs `_TZ`, `VARIANT` for semi-structured, FK/unique informational only (flag).

### Node 3 — ScriptGenerator (LLM + templates, step_order=3, runs AFTER the gate)
- **Responsibility:** emit migration SQL artifacts from the **human-approved** mapping. Never executes anything (analysis_only).
- **Inputs:** `TypeMapperOutput` (mapping.json) + `analyzed-source-schema.json` (`upstream_agents=["migration-agent-schema-analyst","migration-agent-type-mapper"]`) + `target_connector_type`.
- **Mechanics:** thin sync `def` activity wrapping `_execute(agent_code="migration-agent-script-generator", skill_name="migration-generate-scripts", output_model_name="ScriptGeneratorOutput", ...)`. Template skeleton is deterministic; the LLM fills dialect idioms and stubs flagged objects.
- **Outputs / artifacts:** three artifacts via three `write_artifact` calls (so the artifacts API lists each — `write_artifact` slugs one filename per call): `target-ddl.md` (CREATE TABLE/SEQUENCE/CONSTRAINT/INDEX), `data-migration.md` (INSERT…SELECT / COPY / stage templates with explicit per-column CAST), `rollback.md` (DROP/restore). Each wraps fenced ```sql. For flagged PL/SQL/trigger items, emit `TODO` comment stubs + populate `ScriptGeneratorOutput.manual_steps`. Recommended `phase="implementation"` to separate generated SQL from analysis markdown (`implementation_root_for_project` exists; the artifact-content allowlist pins to roots, serves either — `agent_workflows.py:102-152`).
- **Execution guard:** must call `is_execution_enabled()` (§4) and refuse to *run* SQL — but in v1 ScriptGenerator only *writes* scripts, so the guard primarily documents intent; the real guard is on the optional future executor (§4).

### Node 4 — Reconciler (DETERMINISTIC, step_order=4)
- **Responsibility:** compare the PRE-EXISTING source vs target. No LLM. Does NOT run the generated scripts.
- **Inputs:** the table list from `analyzed-source-schema.json` + both connector configs.
- **Mechanics:** sync `def` activity that loops the in-scope tables calling the EXISTING engines: `recon_service.run_row_count_recon` (`backend/app/services/recon_service.py:18`, per-table source-vs-target `COUNT(*)`) and `validation_service.run_schema_compare` (`backend/app/services/validation_service.py:22`, added/removed/type_diff). Both are `async` and take a DB `Session`. The activity opens a worker-local `SessionLocal` (`worker/db/session.py`, as `persist_workflow_step_activity` does) and wraps the async calls in `asyncio.run(...)` per table (or aggregates into one event loop). **Worker-side caveat:** these services live in `backend/app/services/*` and import `app.models.validation` (`ReconRun`/`ReconResult`) which the worker can import (the worker already imports `app.models.workflow`). `connector_service` is backend-only — `recon_service` imports `connector_service.get_row_count`. v1 decision: **port the thin row-count + schema-compare diff into the worker** (≈40 lines) using the worker's own `_build_connector`, writing `ReconRun`/`ReconResult` directly, rather than importing backend services into the worker. This keeps the worker's `app.services.*`-free invariant (`bmad_node_activities.py` only imports `app.models.*`).
- **Outputs / artifacts:** `reconciliation-report.md` via `write_artifact(agent_code="migration-agent-reconciler", skill="migration-reconcile-verify", filename="reconciliation-report", phase="migration")` summarizing per-table `{source_count, target_count, diff, passed}` + schema_compare deltas + overall pass/fail + `verified_pct`. Stamp `recon_run_id` into frontmatter. Also writes ONE `ReconRun` + MANY `ReconResult` rows (`result_type` is a free `String(50)` — `validation.py:44` — so `row_count`, `schema_parity`, and future `column_checksum`/`value_sample_diff` need NO migration). Return `parsed={recon_run_id, verified_pct, per_check_summary}` so it surfaces in both `workflow_steps` (chain view) and `recon_runs`/`recon_results` (compliance view, `backend/app/api/compliance.py`).

| Node | LLM? | Reuses | New code |
|---|---|---|---|
| SchemaAnalyst | No | connector classes, artifact_store, SourceSchemaSnapshot | activity + fan-out loop |
| TypeMapper | Yes | `execute_agent_skill`, artifact_store, gate | activity + SKILL.md + `TypeMapperOutput` |
| ScriptGenerator | Yes | `execute_agent_skill`, artifact_store | activity + SKILL.md + `ScriptGeneratorOutput` |
| Reconciler | No | recon row-count + schema-compare logic, ReconRun/Result | activity + per-table loop |

---

## 3. Coexistence Plan — exact new / edited files

### 3.1 NEW — `worker/workflows/migration_per_node_workflow.py`
Clone of `worker/workflows/bmad_per_node_workflow.py`. Define `@workflow.defn class MigrationPerNodeWorkflow` keeping VERBATIM: `__init__` state (`_approval_decision/_approval_notes/_current_step/_outputs/_artifact_paths`), `@workflow.signal approve/reject` (lines 103-111), `@workflow.query current_step/outputs/artifact_paths`, the inner `run_step(fn, agent_key, step_order)` helper (lines 161-213), `reconcile_terminal_state(status, summary)` (lines 134-159), the per-agent `RetryPolicy`/`_ACTIVITY_TIMEOUT`/`_PERSIST_TIMEOUT`/`_APPROVAL_TIMEOUT` constants, and `run_id = input_data.get("workflow_run_id", workflow_id)` (line 132). Import the 4 new activities under `with workflow.unsafe.imports_passed_through():` (line 35) plus the 2 reused persist activities. Replace the 13 phase calls with:
```
step1: schema_analyst_activity        agent_key="schema_analyst"      step_order=1
step2: type_mapper_activity           agent_key="type_mapper"         step_order=2
        ── approval gate: workflow.wait_condition(_approval_decision is not None, 48h) ──
        on timeout → reconcile_terminal_state("expired"); on reject → "rejected"
step3: script_generator_activity      agent_key="script_generator"    step_order=3
step4: reconciler_activity            agent_key="reconciler"          step_order=4
        terminal → reconcile_terminal_state("completed")
```
Gate placement is AFTER TypeMapper (study's recommendation: human signs off mapping before any DDL is generated). Distinct class name = distinct Temporal workflow type. Keep it strictly deterministic (no I/O in workflow code).

### 3.2 NEW — `worker/activities/migration_node_activities.py`
Four `@activity.defn` sync `def` functions:
- `schema_analyst_activity(input_data)` — deterministic fan-out (§2 Node 1), wrapped in `_run_with_heartbeats`. Imports the connector factory + `artifact_store.write_artifact` + `app.models.schema_snapshot.SourceSchemaSnapshot` + worker `SessionLocal`.
- `type_mapper_activity(input_data)` — `_execute("migration-agent-type-mapper", "migration-map-types", "TypeMapperOutput", input_data, upstream_agents=["migration-agent-schema-analyst"], artifact_filename="type-mapping")`.
- `script_generator_activity(input_data)` — `_execute("migration-agent-script-generator", "migration-generate-scripts", "ScriptGeneratorOutput", input_data, upstream_agents=["migration-agent-schema-analyst","migration-agent-type-mapper"], artifact_filename="target-ddl")` (and two further `write_artifact` calls for data/rollback, or have the skill emit all three and the activity write each).
- `reconciler_activity(input_data)` — deterministic per-table row-count + schema-compare (§2 Node 4), writes ReconRun/ReconResult + report artifact.

Refactor note: factor `_run_with_heartbeats`, `_safe_heartbeat`, `_heartbeat_pool`, `_execute` out of `bmad_node_activities.py` into a shared `worker/activities/_executor_support.py` and import from both, to avoid copy-paste. This is a refactor of existing functions (no behavior change) — low risk, but optional; copy-paste is acceptable for v1 if the refactor widens the blast radius.

**Reused unchanged:** `persist_workflow_step_activity`, `persist_workflow_terminal_state_activity` (`bmad_node_activities.py:414,467`).

### 3.3 NEW — `agents/helix_migration.py` (+ edit `agents/__init__.py`)
`HelixMigration` mirroring `HelixBMAD` (`agents/helix.py`). Differences:
- `workflow_id` property → `f"mig-{self.project_id}-{self.requirement_id}"` (vs `bmad-...` at `helix.py:130-132`). The `mig-`/`bmad-` prefixes never collide on the unique `workflow_runs.workflow_id` index.
- `start_temporal()` → `client.start_workflow(MigrationPerNodeWorkflow.run, self._input_payload(), id=self.workflow_id, task_queue=self.task_queue)` on the SAME `task_queue`.
- `_input_payload()` extended with `source_connection_id, target_connection_id, source_connector_type, target_connector_type, source_config, target_config, in_scope_schemas`.
- Keep `workflow_run_id` UUID generation (`helix.py:118`) and `correlation_id` propagation identical so the run-id contract holds.
- `resume()` / `get_temporal_status()` identical (signal names `approve`/`reject`).
Edit `agents/__init__.py` to also export `HelixMigration` (currently exports only `HelixBMAD, HelixBMADResult` — verified).

### 3.4 NEW — 4 Pydantic output schemas in `agents/bmad/schemas.py`
Append (so `getattr(bmad_schemas, name)` resolves — `bmad_node_activities.py:102`). Reuse `RiskItem` (`schemas.py:29`) for severity flagging:
- `SchemaAnalystOutput(summary, schema_count, table_count, column_count, tables: list[...], risks: list[RiskItem], artifacts: list[ArtifactRef])`.
- `ColumnMapping(source_type, target_type, lossy: bool, ambiguous: bool, requires_review: bool, rationale: str)`.
- `TypeMapperOutput(summary, mappings: list[ColumnMapping], ambiguous_mappings: list[ColumnMapping], approval_required: bool, approval_reason: str, risks: list[RiskItem], artifacts: list[ArtifactRef])`.
- `ScriptGeneratorOutput(summary, ddl_path, data_path, rollback_path, manual_steps: list[str], risks: list[RiskItem], artifacts: list[ArtifactRef])`.
- `ReconcilerOutput(summary, recon_run_id, verified_pct: float, per_table: list[...], schema_parity_passed: bool, overall_passed: bool, artifacts: list[ArtifactRef])`.

### 3.5 NEW — `backend/app/api/migrations.py` (+ edit `backend/app/main.py`)
Router `tags=["migrations"]`, `POST /projects/{project_id}/migrations`, wrapped `@idempotent("start_migration")` (mirror `@idempotent("start_workflow")` at `agent_workflows.py:156`). Request body: `{requirement_id, source_connection_id, target_connection_id, requirement_text?}`. Handler:
1. `ensure_project_access(db, org_id, project_id)`.
2. Validate `MigrationRequirement` exists for `project_id` (mirror `agent_workflows.py:173`).
3. `src_row, src_cfg = project_service.get_source_config(db, org_id, project_id, source_connection_id)` and `tgt_row, tgt_cfg = project_service.get_target_config(...)` (`project_service.py:141,161` — 404 on missing/cross-org). **This decryption MUST happen at the HTTP boundary: the worker imports only `app.models.*`, never `app.services.*`, and has no Fernet key** — so configs are resolved here and passed into the workflow input.
4. `correlation_id = getattr(request.state, "request_id", None)`.
5. `await start_migration_workflow(project_id, requirement_id, organization_id=org_id, requirement_text=..., source_connection_id, target_connection_id, source_connector_type=src_row.connector_type, target_connector_type=tgt_row.connector_type, source_config=src_cfg, target_config=tgt_cfg, db=db, correlation_id=correlation_id)`.
6. Return `StartWorkflowResponse`-shaped `{workflow_id, run_id, status, mode}`.

**SECURITY NOTE (must be in the doc + code comment):** decrypted DB credentials now flow into Temporal workflow history (persisted) and worker memory. Gate all execution under `SAFE_EXECUTION_MODE` (default `analysis_only`): ScriptGenerator only emits SQL, Reconciler only reads. The artifact `_safe_frontmatter` scrubber (SEC-011, `artifact_store.py:275`) strips secrets from frontmatter — ensure configs are never written into artifact bodies either.

Edit `backend/app/main.py`: add `app.include_router(migrations_router, prefix="/api/v1")` alongside the others (`main.py:327-354`).

### 3.6 EDIT — `backend/app/services/workflow_service.py`
Add `start_migration_workflow(...)` mirroring `start_bmad_planning_workflow` (lines 36-123): same cost-cap guard (lines 56-68), Temporal-first then dev/local fallback, then `_persist_started_workflow` with `kind="migration"`. Build `HelixMigration` instead of `HelixBMAD`. **Reuse `create_workflow_run` / `_upsert_workflow_run` / `get_workflow_status` unchanged**, adding only a `kind` kwarg (default `"bmad"` so BMAD callers are byte-for-byte unchanged). Thread `kind` into `_persist_started_workflow` and `create_workflow_run` (lines 200-215, 375-404).
**Also fix the cosmetic mode heuristic** at line 148 (`"bmad-" in workflow_id`): for the not-found branch, prefer reading `run.mode` (already returned at line 189) so a `mig-` id isn't mislabeled `local_fallback`. Cosmetic-only; do it for correctness.

### 3.7 EDIT — `worker/main.py`
Additive only:
- Import `MigrationPerNodeWorkflow` and the 4 new activities.
- `workflows=[BMADPlanningWorkflow, BMADPerNodeWorkflow, MigrationPerNodeWorkflow]` (line 157).
- Append the 4 new activities to `activities=[...]` (line 158-174); keep the 2 persist activities (already present).
- Keep `TASK_QUEUE` unchanged. Update the startup log string (line 192-201) to name the new workflow.

### 3.8 SCHEMA — new Alembic migration + model edit
- NEW `backend/alembic/versions/<hash>_workflow_run_kind.py` with `down_revision = "v3w4x5y6z7a8"` (verified current head). Adds `workflow_runs.kind = Column(String(20), nullable=False, server_default="bmad")`.
- EDIT `backend/app/models/workflow.py:10-23`: add `kind = Column(String(20), default="bmad", nullable=False)` to `WorkflowRun`. **Verify the worker picks up the new column** — the worker imports `app.models.workflow.WorkflowRun` directly (`bmad_node_activities.py:496`); a model/DB mismatch would break terminal-state reconcile. `WorkflowStep` needs NO change (agent_name/step_order carry the migration node names; `parsed_output_json` is generic).
- `mode` stays `"temporal"|"local_fallback"` — **do not overload it** as a family discriminator.

### 3.9 NEW — 4 BMAD-style agent + skill definitions on disk
Two skill dirs discoverable by `_find_skill_dir` (`bmad_loader.py:200`, globs `bmm-skills/[0-9]-*/<skill>` then `core-skills/<skill>`): `migration-map-types/` and `migration-generate-scripts/`, each with `SKILL.md` + `customize.toml`. SchemaAnalyst/Reconciler are deterministic so they need no skill files. Agent codes `migration-agent-type-mapper` / `migration-agent-script-generator` map through `_agent_phase`'s default `"Implementation"` (verified at `bmad_loader.py:197`) — no dict edit required, but a SKILL dir must exist under a phase folder or `core-skills`. The `migration-map-types/SKILL.md` encodes the rule tables from §2 Node 2.

### 3.10 FRONTEND — edit `frontend/src/lib/workflows/api.ts` + the agents page
- Add `startMigration(projectId, body)`: `POST ${API_BASE}/api/v1/projects/${projectId}/migrations`, `credentials:"include"`, JSON body `{requirement_id, source_connection_id, target_connection_id, requirement_text}`, plus an `Idempotency-Key` header (matches `@idempotent`). There is currently NO `startWorkflow` helper in this file (verified) — `startMigration` is purely additive. Returns `{workflow_id, run_id, status, mode}`.
- The "Generate migration" button (in `frontend/src/app/agents/page.tsx`) calls `startMigration`, then immediately calls the EXISTING `subscribeToWorkflow(null, workflow_id, onStep, onDone)` (`api.ts:75-115`) — no SSE/client changes, since `/stream` + `/agent-workflows/{id}` are family-agnostic (key on `workflow_id`).
- Optional: extend `WorkflowRun` TS interface + `WorkflowRunSummary` (backend) to echo `kind` for UI filtering — additive, non-breaking.

---

## 4. Reconciler + Execution Model (dry-run default)

**Default state: nothing can mutate a target.** Every connector method today is read-only (SELECT/COUNT only; a grep for INSERT/UPDATE/DELETE/CREATE/DROP across `connectors/` returns nothing). `SAFE_EXECUTION_MODE="analysis_only"` is the single kill-switch — declared at `config.py:65`, consumed nowhere today. This spec makes it the contract:

- NEW `worker/activities/execution_guard.py` exposing `is_execution_enabled()` → `settings.SAFE_EXECUTION_MODE.lower() not in {"analysis_only","dry_run",""}`. Every write-capable activity MUST call it first and raise `ApplicationError(non_retryable=True)` when disabled.
- **v1 semantics:** ScriptGenerator WRITES scripts to the artifact store, never executes. Reconciler reads source+target via the read-only path and compares the PRE-EXISTING target. No write path ships in v1.
- **recon_runs / recon_results data flow:** Reconciler creates ONE `ReconRun` (`status="running"` → `completed`/`failed`) and MANY `ReconResult` rows — one per check per table. `result_type` is a free `String(50)` (`validation.py:44`) so `"row_count"`, `"schema_parity"`, and the future `"column_checksum"`/`"value_sample_diff"` need NO migration. Keep `summary` as the JSON verdict; point `details_ref` (`String(500)`, `validation.py:50`) at a sample-diff artifact so production row data never lands in Postgres (preserves the metadata-only contract at `recon_service.py:27`). `mismatch_count` is `BigInteger` (handles >2.1B row diffs).
- **`verified_pct` (the "98.7%" number):** v1 = row-count parity per table + schema_parity (binary, deterministic, exists). A real weighted score needs L2 (column-level aggregate checksums) + L3 (sampled row diffs) which require NEW read-only connector primitives `column_checksum(...)` and `fetch_sample(...)` on `BaseConnector` (`connectors/base/connector.py:131-149` declares only test/list_schemas/list_tables/list_columns/get_row_count). **Defer L2/L3 to A2-6.** Persist the score components in the report artifact so the number is auditable. Honor `capabilities.supports_recon` (`connector.py:33`) before scheduling L2/L3.
- **Future optional write path (default OFF, A2-7):** exactly ONE new `apply_migration_script_activity`, AFTER the approval gate, gated on ALL of: `is_execution_enabled()`; a new `"migration:execute"` permission in `auth_service.SYSTEM_PERMISSIONS`; the human approval signal; per-statement explicit transaction + `statement_timeout` + dry `EXPLAIN`/parse first; `write_audit` before+after with the script artifact hash. Needs a new connector `execute_script(sql, *, read_only=True)` that defaults to `BEGIN; ... ; ROLLBACK`. Reuse SSRF host pinning (`_enforce_host_allowlist`, `connectors.py:105-148`) and identifier validation (`connectors/base/identifiers.py`).

---

## 5. Reuse Table

| Existing thing | File ref | Reused as |
|---|---|---|
| Temporal client/worker, task queue | `worker/main.py:56,145-175` | **As-is** (append 1 workflow + 4 activities) |
| Per-node workflow scaffold | `worker/workflows/bmad_per_node_workflow.py:90-308` | **Cloned** → `migration_per_node_workflow.py` |
| `run_step()` helper | `bmad_per_node_workflow.py:161-213` | **As-is** (verbatim) |
| Approval gate (approve/reject signals, 48h wait_condition) | `bmad_per_node_workflow.py:103-111,237-272` | **As-is** |
| `persist_workflow_step_activity` | `bmad_node_activities.py:414-464` | **As-is** (agent-name agnostic) |
| `persist_workflow_terminal_state_activity` | `bmad_node_activities.py:467-541` | **As-is** |
| `_run_with_heartbeats` / `_execute` | `bmad_node_activities.py:84-126,157-180` | **Reused** (factor to shared module or copy) |
| `execute_agent_skill` transport stack | `agents/runtime/bmad_executor.py` | **As-is** (new agent_codes) |
| `getattr(bmad_schemas, name)` output-model resolution | `bmad_node_activities.py:99-102` | **As-is** (new schema classes) |
| `_find_skill_dir` / `_agent_phase` | `bmad_loader.py:188-212` | **As-is** (default "Implementation"; add SKILL dirs) |
| `artifact_store.write_artifact` + collect context + allowlist | `artifact_store.py:239-320`; `agent_workflows.py:102-152` | **As-is** (`.md` wrap for JSON/SQL) |
| `WorkflowRun`/`WorkflowStep` tables | `backend/app/models/workflow.py:10-48` | **Extended** (`WorkflowRun.kind`; step rows unchanged) |
| `create_workflow_run` / `_upsert_workflow_run` (run_uuid pin) | `workflow_service.py:224-404` | **Extended** (add `kind` kwarg, default `"bmad"`) |
| `get_workflow_status` | `workflow_service.py:126-194` | **As-is** (fix line-148 mode heuristic, cosmetic) |
| `start_bmad_planning_workflow` | `workflow_service.py:36-123` | **Cloned** → `start_migration_workflow` |
| `HelixBMAD` facade | `agents/helix.py` | **Cloned** → `HelixMigration` (`mig-` prefix) |
| Trigger endpoint pattern + `@idempotent` | `agent_workflows.py:155-198` | **Cloned** → `migrations.py` |
| GET status / artifacts / artifact-content / approve / signal-approve / signal-reject / stream | `agent_workflows.py:201-557` | **As-is, ZERO changes** (key on workflow_id) |
| `project_service.get_source_config` / `get_target_config` | `project_service.py:141-174` | **As-is** (decrypt at HTTP boundary) |
| Connector discovery (`discover_schemas/tables/columns`, `get_row_count`) | `connector_service.py:56-73` | **As-is** (SchemaAnalyst owns fan-out) |
| `recon_service.run_row_count_recon` + `run_schema_compare` logic | `recon_service.py:18`; `validation_service.py:22` | **Reused** (port thin logic worker-side) |
| `ReconRun`/`ReconResult` models | `validation.py:32-50` | **As-is** (free `result_type`, BigInteger) |
| `SourceSchemaSnapshot` + drift diff + `SchemaDriftCard` | `schema_snapshot.py:14`; `schema_drift.py`; `frontend/.../SchemaDriftCard.tsx` | **Reused** (src/tgt snapshots, parity diff) |
| `SAFE_EXECUTION_MODE` | `config.py:65` | **Activated** as the kill-switch (was inert) |
| `subscribeToWorkflow` SSE client | `frontend/src/lib/workflows/api.ts:75-115` | **As-is** |
| pair-review (already migration-flavored prompt) | `workflow_ops.py:268-275` | **As-is** for reviewing generated DDL |

---

## 6. Risks / Regressions to BMAD + Mitigations

1. **Worker boot crash takes BMAD down.** Temporal validates workflow + activity registration at worker start; a malformed `MigrationPerNodeWorkflow` import in `worker/main.py` crashes the single worker and BMAD with it. → Keep the workflow strictly deterministic, imports under `workflow.unsafe.imports_passed_through()` (mirror `bmad_per_node_workflow.py:35`), reference activities by function symbol; add a worker-boot smoke test asserting all THREE workflow types register (A2-1 gate).
2. **SSE never closes for `expired`.** The `done` set at `agent_workflows.py:466` is `("completed","approved","rejected","failed")` — `expired` is absent (verified). The migration gate can emit `expired` on 48h timeout. → **Decision: reuse the same status vocabulary** (emit `failed`/`rejected`, not `expired`) OR add `"expired"` to that tuple. Pick the latter only if you also fix the BMAD path's identical caveat; for v1, reusing the vocabulary is lower-risk. The migration workflow MUST reconcile to a status in that set or the stream hits the 120s timeout.
3. **`get_workflow_status` mislabels `mig-` ids as `local_fallback`.** The not-found branch infers mode from `"bmad-" in workflow_id` (line 148). → Cosmetic; fix by reading `run.mode` (already at line 189). Harmless if deferred.
4. **`replay_workflow` spawns the wrong family.** `workflow_ops.replay_workflow` hardcodes `start_bmad_planning_workflow` and `_validate_prompt_overrides._VALID_AGENT_CODES` rejects the new migration agent codes (study refs `workflow_ops.py:69-127,130-194`). → Make replay `kind`-aware: branch on `parent.kind`, dispatch to `start_migration_workflow`, and add the 4 migration agent codes to `_VALID_AGENT_CODES`. **Deferrable** — v1 can 409 "replay not supported for migration runs". Not a blocker.
5. **`workflow_id` collision.** Unique index on `workflow_runs.workflow_id`. → `mig-`/`bmad-` prefixes are immutable and never collide.
6. **DB credentials in workflow history.** Decrypted configs persist in Temporal history. → `SAFE_EXECUTION_MODE` default keeps everything read-only; SEC-011 frontmatter scrubber prevents leakage into artifacts; consider (A2-7) wiring the Fernet key into the worker and passing connection IDs instead of raw configs.
7. **Run-id FK violation.** If `HelixMigration` doesn't pin `run_uuid` into both `create_workflow_run` and `input_data["workflow_run_id"]`, the 4 step inserts violate `workflow_steps.workflow_run_id_fkey`. → Mirror the BMAD contract exactly (`workflow_service.py:391`, `helix.py:118`, `bmad_per_node_workflow.py:132`).
8. **Approve/signal endpoints.** They signal by `workflow_id` generically (`agent_workflows.py:324-339`) and require the workflow to define `approve`/`reject` signals with matching names — the clone does. No change, no regression.

---

## 7. Ordered A2 Milestone Breakdown (smallest shippable first)

**A2-1 — Skeleton echo chain, end-to-end, no LLM, no real DB.** Add `MigrationPerNodeWorkflow` with 4 activities that return canned `{success:True, parsed:{...}, artifact_path:None}` dicts (no connector/LLM calls). Register in `worker/main.py`. Add `HelixMigration` + `start_migration_workflow` (`kind="migration"`) + `POST /projects/{id}/migrations`. Add the `workflow_runs.kind` migration + model field. **Acceptance:** POST starts a `mig-...` run; worker boots with all 3 workflow types (smoke test); 4 `workflow_steps` rows persist; gate pauses after step2; `/approve` resumes; `/stream` emits 4 `step` frames + `done`; terminal status reconciles. Proves the orchestration seam with zero external dependencies and zero BMAD regression.

**A2-2 — Real SchemaAnalyst (deterministic introspection).** Replace step1 echo with the connector fan-out (`list_schemas→list_tables→list_columns→get_row_count`) for existing connectors (postgres first). Write `analyzed-source-schema.json` (`.md`-wrapped) + a `SourceSchemaSnapshot` row. Wrap in `_run_with_heartbeats`. **Acceptance:** a real postgres source produces a schema artifact + snapshot row; serves through `/artifact-content`.

**A2-3 — Real TypeMapper (LLM) + approval gate semantics.** Author `migration-map-types/SKILL.md` (rule tables from §2 Node 2) + `TypeMapperOutput`. Replace step2 echo with `_execute(...)`. `approval_required=true` when any mapping is lossy/ambiguous; `ambiguous_mappings` surface in `WorkflowStep.parsed_output_json` for the reviewer. **Acceptance:** postgres→postgres (or →snowflake) mapping produces `type-mapping.md`; gate trips on ambiguity; reviewer approves; chain proceeds.

**A2-4 — Real ScriptGenerator (LLM+templates).** Author `migration-generate-scripts/SKILL.md` + `ScriptGeneratorOutput`. Emit `target-ddl.md`/`data-migration.md`/`rollback.md` (three `write_artifact` calls, `phase="implementation"`); flagged PL/SQL→`manual_steps`. Wire `is_execution_enabled()` guard (writes only). **Acceptance:** three SQL artifacts listed by `/artifacts`; nothing executed against any target.

**A2-5 — Real Reconciler (deterministic).** Replace step4 echo with per-table row-count + schema-compare (ported worker-side), ONE `ReconRun` + MANY `ReconResult` rows + `reconciliation-report.md` with `verified_pct` (row-count + schema_parity only). **Acceptance:** recon report artifact + recon rows; surfaces in compliance PDF; `verified_pct` computed and auditable.

**A2-6 — Deep introspection + L2/L3 reconciliation (closes the type-shallow gap).** Extend `ColumnInfo` + each connector's column read to carry precision/scale/default; add `list_constraints`/`list_indexes`/`list_sequences` and `column_checksum`/`fetch_sample` read-only primitives + discovery endpoints. Weighted `verified_pct` blend (L1 row-count gate + L2 checksum ratio + L3 sample match ratio). **Acceptance:** ScriptGenerator can emit correct `NUMBER(p,s)`/PK/FK/sequence DDL; "98.7%" is a real weighted, auditable number.

**A2-7 — Oracle connector + optional guarded executor (default OFF).** Add `connectors/oracle/connector.py` (`ConnectorType.ORACLE`, `BUILTIN_CONNECTORS` entry) surfacing NUMBER precision/sequences/identity/constraints/triggers/PL-SQL inventory (`ALL_TAB_COLUMNS`/`ALL_CONSTRAINTS`/`ALL_SEQUENCES`/`ALL_TRIGGERS`/`ALL_SOURCE`). Optionally add the single `apply_migration_script_activity` behind ALL guards in §4. Make `replay_workflow` `kind`-aware (Risk #4). **Acceptance:** Oracle→Postgres source introspects; execution remains impossible unless `SAFE_EXECUTION_MODE` is explicitly flipped AND the new permission + approval are present.

---

### Build-order summary
A2-1 ships the whole seam (echo). A2-2…A2-5 fill the four nodes left-to-right with real logic. A2-6/A2-7 close the two CRITICAL GAPS (type-shallow discovery, no Oracle) and add the optional write path. Each milestone is independently shippable and BMAD stays byte-for-byte unchanged throughout because every edit is additive (one workflow in the list, four activities, one nullable column, one new router, one cloned facade/service).
