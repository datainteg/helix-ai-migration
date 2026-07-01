# Helix → Enterprise Data Migration & Modernization Platform — Architecture Review & Proposal

## Context

The user owns `helix-ai-migration/` (GitHub `datainteg/helix-ai-migration`) and wants to turn it into a **commercial, enterprise-grade Data Migration & Modernization Platform** specialized in **IBM DataStage / SAS / legacy → cloud** migrations — with a plugin-based connector architecture, a reusable migration engine, AI assistance throughout, enterprise security/scalability, and a premium UI.

**Decisions locked with the user:**
- **Build strategy:** *Evolve* the existing Helix shell (reuse auth, RBAC, audit, encryption, Temporal, Next.js UI, connector registry, BMAD agents). Do **not** greenfield.
- **Conversion philosophy:** *Deterministic transpiler + AI assist* — parse → canonical IR → deterministic code generators; AI assists for ambiguity/explanation/gap-fill (never the sole source of truth).
- **Phase-1 vertical slice:** **Legacy table/view → Snowflake + reconciliation** (the highest-volume real pattern).
- **Source reality (from real tickets):** "Bedrock"/"Core" = legacy on-prem **EDW on IBM DB2 / mainframe**; primary target = **Snowflake**; also Databricks, Airflow, vendor files (Experian/Acxiom). DataStage jobs present (`sq_` jobs, port-file SQL, sequences).
- **Tracking:** *Both* — native migration tracking **and** Jira sync (tickets look like `DPE-####`).
- **Assets:** User has real `.dsx`/`.isx` exports **and** a live DataStage environment for parser validation.

**Intended outcome:** A core architecture where new source/target systems and migration scenarios are added as **plugins** with **minimal core changes**, anchored by a deterministic migration engine and the existing enterprise shell.

**North Star (the product's success metric):** *measurably reduce end-to-end migration cycle time and increase team productivity using AI* — across **data migration, DataStage migration, and other migration types** — with **living documentation**, **validation**, and **reconciliation** as first-class, non-negotiable quality gates, and **Jira as the system of record** (every migration unit ↔ a `DPE-####` ticket). The platform is judged by *time saved per migration* and *automation %*, not feature count. See **B7**.

> ⚠️ This document is the **pre-implementation architecture** (the 15 requested deliverables). No code is to be written until approved.

---

## 1. Current Codebase Review (what actually exists)

**Verdict: Helix today is an AI _planning & documentation_ pipeline with an enterprise shell — NOT a migration _execution_ engine.**

### Strong, reusable shell (~60% of enterprise plumbing already done)
| Area | Reality | Reuse? |
|---|---|---|
| **Backend** | FastAPI, 29 routers, 22 services, 17 model files, 28+ Alembic migrations | ✅ Keep & extend |
| **Auth/Security** | JWT (cookie+bearer), RBAC (6 roles × 17 perms), Fernet + per-org DEK envelope encryption, HMAC-chained audit log, SSRF guards, rate limiting | ✅ Keep; add SSO/MFA/secrets-mgr |
| **Orchestration** | Temporal worker; durable workflows, signals, 48h approval gate, heartbeats, retry policies | ✅ Reuse as engine orchestrator |
| **Connector registry** | `BaseConnector` ABC + custom registry (`register_connector`) + builtin dispatch in `connector_service.py` | ✅ Extend to v2 plugin contract |
| **AI framework** | BMAD 6-agent + LangGraph 13-node graph; per-agent LLM routing (10 providers); PydanticAI→httpx→mock fallback | ✅ Repurpose as AI-assist layer |
| **Frontend** | Next.js 14 App Router, **80+ routes**, ReactFlow DAG, dark mode, 40-component design system, Zustand+React Query | ✅ Keep; add migration screens |
| **Deploy** | Docker Compose (9 services), Caddy TLS, one-command installer | ✅ Keep; add scale story |

### The missing core (the actual product)
- **Connectors are read-only metadata**: only `test_connection / list_schemas / list_tables / list_columns / get_row_count`. No data read/write, no job parsing, no deploy, no rollback. (`connectors/base/connector.py`)
- **No migration execution**: the 13 agents call an LLM and write **markdown**. `amelia_dev` emits code *as text*, never compiled/run. (`agents/runtime/bmad_executor.py`)
- **No DataStage/SAS parsing**: zero `.dsx`/`.isx`/`.sas` handling, no AST, no transpilation, no type mapping. `static_analysis.py` is Python-QA only.
- **"Validation/recon/CDC" are metadata-only**: row-count compares + "we checked at T" markers. No data reconciliation. (`validation_service.py`, `recon_service.py`, `cdc_engine.py`)
- **Cutover** is a state-machine of metadata; operators run real migrations *outside* Helix and report status back.

### Connector interface vs the 12 required operations
| Operation | Status today |
|---|---|
| Connection mgmt, Auth, Metadata extraction, Schema discovery | ⚠️ Partial/Full (read-only) |
| Data type mapping | ⚠️ Minimal (free-text `data_type` only) |
| Validation | ⚠️ Minimal (connectivity + row count) |
| **Job parsing, Dependency analysis, Transformation conversion, Deployment, Testing, Rollback** | ❌ **Missing entirely** |

---

## 2. Architecture Review

- **Layering is sound**: clean separation (API → services → models; agents runtime; worker activities; connectors package). Good base to extend.
- **Multi-tenancy & security are genuinely enterprise-grade** for what exists (per-org isolation, envelope encryption, tamper-evident audit).
- **Temporal is the right orchestration substrate** for long-running, resumable, signal-driven migrations — currently underused (only sequences LLM calls).
- **Connector registry is the right extensibility seam** but the interface is far too thin (read-only, single fat ABC).
- **The AI layer is mis-cast**: it *is* the engine today; it should become an *assist* layer around a deterministic core.
- **Frontend is ahead of the backend**: many enterprise screens exist as shells without a real engine behind them.

---

## 3. Identified Issues, Risks & Technical Debt

**Architectural**
1. **No execution engine** — the central gap; everything below depends on building it.
2. **Fat connector ABC** — one interface forces every connector to fit a DB-table shape; DataStage/SAS/files don't.
3. **No canonical data-type system** — `data_type: str` can't drive deterministic DB2→Snowflake mapping.
4. **No IR / lineage model** — can't do dependency graphs, impact analysis, or N+M (vs N×M) target support.
5. **AI as source of truth** — non-deterministic, unauditable for 1000s of jobs.

**Scalability**
6. Single-instance defaults (DB pool 10+20; worker 5 concurrent activities; Temporal single server). No horizontal-scale or distributed data-movement story.
7. No execution backend for large data (no Spark/dbt/Snowflake-bulk integration).

**Security (enterprise gaps)**
8. No **SSO (SAML/OIDC/OAuth)**, no **MFA/TOTP**, no **external secrets manager** (KEK lives in `.env`), no session-management UI, no approval workflow on admin/secret ops.

**Product/ops**
9. No native↔Jira sync. 10. Monitoring is env-var stubs (Sentry/OTEL) — no dashboards/alerts. 11. Scheduling Center, real-time activity feed, AI copilot chat — UI gaps.

---

## 4. Proposed Enterprise Architecture

**Principle:** a deterministic **Migration Engine** built on a canonical **Intermediate Representation (IR)**, with **capability-segregated plugins** for sources and targets, AI as an assist layer, all riding the existing Temporal + enterprise shell.

```
┌──────────────────────────── Next.js 14 Enterprise UI (existing + new screens) ────────────────────────────┐
└───────────────────────────────────────────────┬──────────────────────────────────────────────────────────┘
                                                 │ REST/SSE (existing FastAPI shell: auth, RBAC, audit)
┌────────────────────────────────────────────────▼─────────────────────────────────────────────────────────┐
│                                        MIGRATION ENGINE CORE (new)                                          │
│  Metadata Extractor → IR Builder → Dependency Graph → Impact Analyzer → Type-Mapping Registry →             │
│  Transform Mapper → Target Code Generator → Data Mover (batch/incremental/parallel, checkpoint/resume) →    │
│  Validator (schema+data) → Reconciliation → Deployer (+ Rollback journal) → Dry-run → Report/Version-diff   │
│                              ▲ AI ASSIST (explain, recommend, gap-fill, map, optimize)                      │
└───────┬───────────────────────────────────────┬──────────────────────────────────────────┬────────────────┘
        │ Source Plugins (parse→IR)              │ Canonical IR (typed, versioned)           │ Target Plugins (IR→code/deploy)
  DB2/Mainframe · DataStage(.dsx) · SAS · ...    │ Datasets·Jobs·Transforms·Lineage·Params   │ Snowflake · Databricks · Airflow · S3 · Files · DataStage(new)
        └───────────────────── Temporal durable orchestration (existing worker, extended) ──┘
```

**Why this scales to "all paths without refactor":** sources parse **into** IR; targets generate **from** IR ⇒ adding a system is **N+M adapters, not N×M** conversions.

---

## 5. Database Design (extends existing 17-model schema)

Reuse `Organization/User/Role/Permission/Project`. **Add** (new Alembic migrations, new `backend/app/models/migration*.py`):

- **MigrationProject** (extends Project) — program-level container.
- **MigrationUnit** — one migratable thing (table/view/job/file); fields: `source_system`, `source_ref`, `target_system`, `target_ref`, `unit_type`, `status`, `jira_key`, `complexity_score`, `readiness_score`.
- **MigrationRun** — an execution attempt (dry-run/real); `mode`, `status`, `checkpoint`, `temporal_workflow_id`, metrics.
- **IRGraph / IRNode / IREdge** — persisted canonical IR + lineage (dataset/job/transform nodes, dependency edges).
- **TypeMapping** — per source→target dialect type rules (DB2 `DECIMAL(p,s)`→Snowflake `NUMBER(p,s)`, etc.); override-able per org.
- **TransformMapping** — IR-transform → target-codegen rule + coverage flag (deterministic vs AI-assisted).
- **ReconResult** (extend existing) — row count + **checksum/hash** + column-stat diffs + sampled-row diffs.
- **DeploymentJournal** — applied DDL/DML + inverse for **rollback**.
- **ConnectorInstance** — registered source/target connection (encrypted config via existing DEK).
- **JiraLink** — native↔Jira mapping + sync state.
- **ImpactEdge** — cross-system "X feeds Y" for blast-radius queries.

---

## 6. Migration Engine Design

Pipeline stages (each a Temporal activity; resumable; dry-run aware):
1. **Extract metadata** (source plugin) → 2. **Build IR** (normalize to canonical model) → 3. **Dependency graph** → 4. **Impact analysis** → 5. **Type mapping** (registry) → 6. **Transform mapping** (deterministic; AI-assist fallback flagged) → 7. **Target codegen** (DDL + load + orchestration) → 8. **Dry-run** (generate + validate, no apply) → 9. **Deploy** (apply DDL; journal inverse) → 10. **Data move** (batch/incremental/parallel; checkpoint/resume) → 11. **Validate + reconcile** (schema, row count, checksum, column stats) → 12. **Report + version compare**; **Rollback** from journal on failure.

**Execution backends (pluggable):** in-process (small), **Snowflake-native bulk** (extract→stage→`COPY`) for Phase 1, later Spark/dbt. Engine *generates and orchestrates*; heavy lifting delegated to target-native loaders.

**Key reuse:** Temporal worker (`worker/`), heartbeat/retry patterns, artifact store for generated code, cost service for AI usage.

---

## 7. Connector Architecture (plugin v2)

Replace the single fat ABC with **capability-segregated interfaces** (a connector implements only what it supports); discovered via a **plugin registry** (extends `connectors/custom/registry.py`) with **versioned contracts** + manifest:

- `MetadataProvider` (exists today) · `DataReader` · `DataWriter` · `JobParser` (→IR) · `DependencyProvider` · `CodeGenerator` (IR→target) · `Validator` · `Deployer` (+ inverse for rollback) · `Tester`.
- Standard `ConnectionContext` (auth, pooling, lifecycle), typed `CanonicalType` system, structured error codes, observability + audit hooks.

**Phase-1 connectors:** **DB2 source** (MetadataProvider+DataReader+DependencyProvider), **Snowflake target** (CodeGenerator+DataWriter+Deployer+Validator). Keep existing 7 connectors working via an adapter shim.

---

## 8. AI Architecture (assist, not drive)

Repurpose BMAD/LangGraph (`agents/`) + per-agent provider routing as an **assist layer** with typed, schema-validated outputs:
- **Code understanding / legacy job explanation** (summarize a `.dsx` stage graph).
- **Mapping recommendations** (suggest type/transform mappings where deterministic rules miss; human-approved → promoted to deterministic rules).
- **SQL optimization, error/root-cause analysis, doc & test-case generation, dependency narration.**
- **Guardrails:** every AI output is *advisory*, validated against IR/schema, attributed, cost-tracked (existing `cost_service`), and gated by the existing human-approval signal.

---

## 9. UI/UX

Reuse design system + ReactFlow + dark mode. **Existing & adequate:** Dashboard, Projects/Sprints, Dependency graph, Mapping, Validation, Reconciliation, Reports, Audit Logs, User Mgmt, Settings, Connectors. **Add/upgrade:**
- **Migration Workspace** (per unit: source→IR→target side-by-side + diff).
- **Visual Job Graph** for real DataStage jobs (stages/links) — not just sprint deps.
- **Source/Target Explorer** (schema browse), **Migration Wizard** (DB2→Snowflake first), **Reconciliation Center** (checksum/stat diffs), **Run Monitor** (live SSE), **Scheduling Center**, **AI Assistant copilot**, **Impact Analysis** viewer, **Session mgmt** + **SSO/MFA** settings.

Wireframes (low-fi) to be added per screen in implementation Phase 0.

---

## 10. Folder Structure (additions)

```
migration_engine/            # NEW core (pure, framework-free, unit-testable)
  ir/                        # canonical model + types + serialization
  graph/                     # dependency + impact analysis
  mapping/                   # type & transform registries
  codegen/                   # target generators (snowflake/, databricks/, airflow/)
  datamove/                  # extract/stage/load, checkpoint/resume
  recon/                     # schema+data reconciliation
  deploy/                    # apply + rollback journal
  report/                    # migration reports, version diff
connectors/
  contracts/                 # NEW capability interfaces + registry v2
  db2/  datastage/  sas/     # NEW source plugins (datastage parses .dsx→IR)
  snowflake/ (extend) databricks/ airflow/ files/  # targets
backend/app/
  api/migrations.py services/migration_service.py models/migration*.py  # NEW
  integrations/jira/         # NEW native↔Jira sync
worker/workflows/migration_workflow.py  # NEW Temporal migration orchestration
frontend/src/app/migrations/ ...        # NEW screens
```

---

## 11. Technology Recommendations

- **Engine:** Python (matches stack); pure-domain core (no FastAPI/Temporal imports) for testability.
- **DataStage parsing:** `lxml` over `.dsx`/`.isx` XML → IR (validate against user's real exports + live env).
- **SAS parsing:** custom tokenizer/grammar (DATA step, PROC SQL, macros) → IR.
- **DB2:** `ibm_db` / `ibm_db_sa` SQLAlchemy dialect.
- **Snowflake:** `snowflake-connector-python` + external stage `COPY`; **dbt** as optional codegen target later.
- **Reconciliation:** hash/checksum (e.g. per-partition MD5/`HASH_AGG`) + column stats; sampled row diff.
- **Big data (later):** Spark/Databricks Jobs API for volume.
- **Jira:** official REST API + webhooks.
- **Keep:** Temporal, Postgres, Redis, Next.js, PydanticAI.

---

## 12. Security Architecture (close enterprise gaps)

Keep JWT/RBAC/DEK/HMAC-audit. **Add:** **SSO** via `authlib` (OIDC + SAML; Okta/Azure AD/Google presets) · **MFA/TOTP** (`pyotp` + recovery codes) · **External secrets manager** (Vault / AWS Secrets Manager for KEK + connector creds) · **approval workflows** on deploy/rollback/secret-rotation/admin ops (reuse Temporal signal gate) · **session-management** UI + force-logout · **API keys** (scoped, separate from JWT) · per-connector credential isolation (existing DEK) · compliance-ready audit on every migration action.

---

## 13. Scalability Strategy

- **Stateless backend** behind LB → N replicas; Redis already externalizes revocation/sessions.
- **Temporal worker pool** horizontally scaled; per-migration-unit activities → massive parallelism; raise `WORKER_MAX_CONCURRENT_ACTIVITIES`; dedicated task queues per workload class.
- **Queue-based unit processing**: 1000s of units pipelined through Temporal with checkpoint/resume.
- **Delegate data volume** to target-native bulk (Snowflake `COPY`) / Spark — engine orchestrates, doesn't stream rows through itself.
- **DB:** tune pools, use read replicas (already supported) for dashboards; partition large metadata/IR tables.
- **Observability:** wire Prometheus/Grafana + OTEL traces (env hooks exist); per-activity SLAs.
- **K8s:** Helm chart + HPA (CPU/queue-depth) for backend & workers.

---

## 14. Migration Workflow (Phase-1: DB2 → Snowflake + recon)

```
Select MigrationUnit(s) (table/view)            ── native + Jira-linked
  → DB2 connector: extract metadata → IR
  → Type mapping (DB2→Snowflake) [AI-assist on gaps, human-approve]
  → Snowflake codegen: DDL (+ view rewrite)
  → DRY-RUN: validate DDL + plan (no apply)  ── human approval gate (Temporal signal)
  → Deploy DDL (journal inverse)
  → Data move: DB2 extract → stage → Snowflake COPY (checkpointed, resumable, parallel by partition)
  → Reconcile: row count + checksum + column stats (+ sampled diff)  → Report
  → On failure: resume from checkpoint OR rollback from journal
  → Sync status → Jira (DPE-####)
```

---

## 15. Implementation Roadmap (phased; no core rewrites between phases)

- **Phase 0 — Foundation (design→scaffolding):** IR model + canonical type system; connector v2 contracts + registry; `migration_engine/` skeleton; new DB models/migrations; UI wireframes. Adapter shim keeps existing connectors working.
- **Phase 1 — DB2→Snowflake + Reconciliation (the proving vertical):** DB2 source connector, Snowflake target (DDL+COPY+deploy+rollback journal), type-mapping registry, data mover (checkpoint/resume), reconciliation engine, migration report, Migration Wizard + Run Monitor + Recon Center UI, native tracking + Jira sync. **Validated against user's live DB2 + real tickets.**
- **Phase 2 — DataStage ingestion:** `.dsx`/`.isx` parser → IR, Visual Job Graph, dependency + impact analysis, DataStage→Snowflake SQL codegen (validated against user's real exports + env).
- **Phase 3 — More targets:** Databricks/PySpark + Airflow generators from the same IR; vendor-file interfaces (Experian/Acxiom: extract→file→SFTP).
- **Phase 4 — SAS→Databricks:** SAS parser → IR → PySpark/Spark SQL.
- **Phase 5 — Enterprise hardening:** SSO/MFA/secrets-manager, K8s/Helm + HPA, Prometheus/Grafana, Scheduling Center, AI copilot, scale tests (1000s of units).

---

## Verification (how each phase is proven)

- **Engine core:** pure unit tests on IR build / type mapping / codegen (golden-file tests vs expected DDL/SQL) — runs with **Python only, no Docker**.
- **Phase 1 end-to-end:** against the user's **live DB2 + Snowflake** — migrate a real table (e.g. a Bedrock class table), then reconcile (row count + checksum match) and confirm rollback restores prior state. Dry-run produces DDL without applying.
- **DataStage parser:** parse the user's real `.dsx` exports; assert IR matches the live DataStage job's stages/links; round-trip subset back and diff.
- **Full stack:** once WSL/Docker is repaired, `docker compose up` and exercise via the new UI + existing Temporal worker.
- **Regression:** existing backend/agents test suites stay green (shim preserves current connector behavior).

> **Open follow-ups before/early in Phase 0:** confirm DB2 flavor (z/OS vs LUW) & driver access; Snowflake account/stage strategy; Jira instance + auth for sync; sample `.dsx` exports to seed the parser corpus.

---
---

# PART B — Enterprise Platform Architecture (Final Review & Enhancements)

**Objective shift:** not a migration *tool* but an **Enterprise Migration & Modernization _Platform_** that can become a long-term commercial SaaS, competing with IBM, Informatica, Microsoft, AWS Migration Hub, Databricks, Snowflake, Oracle. Part A's deterministic-IR core stays; Part B adds the platform capabilities, validates principles, and prioritizes them so foundational primitives are baked in **before** Phase 1 (cheap now, costly to retrofit).

## B1. Architecture Principles — Validation

| Principle | Status in Part A | Enforcement / change in Part B |
|---|---|---|
| **Capability-driven (not migration-pair)** | ✅ IR core | Core MUST NOT import any source/target name; pair logic lives only in plugins. Add a CI lint that fails if `migration_engine/` references a vendor. |
| **Plugin-first** | ✅ connector v2 | Add Marketplace + SDK + signed packages. |
| **API-first** | ⚠️ partial | Design OpenAPI/GraphQL contracts **before** UI; UI consumes same public API. |
| **Event-driven** | ❌ missing | **Add domain event bus** (foundational — see B2). |
| **Domain-driven design** | ⚠️ implicit | Formalize **bounded contexts** (B2); pure domain core in `migration_engine/`. |
| **Multi-tenant SaaS** | ✅ org isolation | Add Departments/Teams/Quotas/Plans/Billing (B3.7). |
| **Cloud-native** | ⚠️ compose only | 12-factor, stateless, K8s/Helm + HPA, externalized secrets. |
| **AI-assisted but deterministic** | ✅ locked | Keep; AI outputs advisory + schema-validated. |
| **Zero vendor lock-in** | ✅ IR neutral | Abstract every external (LLM, event bus, graph store, object store, execution backend) behind a **port**; no proprietary dep in core. |
| **Backward compatibility** | ⚠️ partial | **Version everything**: IR schema, connector contracts, public APIs (semver + deprecation policy). |
| **Horizontal scalability** | ✅ addressed | Per-unit Temporal activities; stateless services; queue-based. |
| **Enterprise security by default** | ⚠️ gaps | SSO/MFA/secrets-mgr/policy engine (B3.6). |

## B2. Capability-Driven Core, DDD Contexts & Event Backbone

**Core guarantee:** `Any Source → Canonical IR → Any Target`. Engine is unchanged when connectors are added; N+M plugins, never N×M. IR is **versioned** and vendor-neutral.

**Bounded contexts (DDD):** each is an independently deployable module with its own models + events:
1. **Identity & Access** (exists) 2. **Connector & Marketplace** 3. **Migration Engine** (IR, assessment, rules, transforms, codegen, datamove, recon, deploy) 4. **Metadata Catalog & Knowledge Graph** 5. **Governance & Compliance** 6. **Observability & Cost** 7. **Billing & Tenancy** 8. **Integration** (Jira, webhooks, events, public APIs).

**Event-driven backbone (NEW, foundational):** an `EventBus` port emitting domain events (`MigrationUnitCreated`, `AssessmentCompleted`, `RunStarted/Progressed/Failed`, `DDLDeployed`, `ReconCompleted`, `ConnectorInstalled`, `PolicyViolated`, …). Consumers: catalog/knowledge-graph sync, observability, webhooks, audit, billing meters, search indexer. **Tech:** start **Redis Streams** (Redis already present) or **NATS**; abstract behind the port so **Kafka** can drop in for scale. Temporal = orchestration; EventBus = integration/notification (don't conflate).

## B3. New Enterprise Subsystems

### B3.1 Connector Ecosystem — Marketplace + SDK
- **Marketplace:** installable, versioned connectors; certification tiers (community/verified/certified); enterprise licensing; **private per-org connectors**; auto-generated docs; ratings. Backed by a `ConnectorPackage` registry + signed artifacts + capability manifest.
- **Connector SDK:** `helix-connector` CLI (scaffold, test, validate, package, publish), project templates, contract-conformance **test harness** (runs capability suites against a connector), validation/linting, semver + compat checks, doc generator, sample connectors. This is what makes the ecosystem (partners/customers) viable.
- **Contract/IR versioning** (foundational): connectors declare `contract_version` + `ir_version`; engine negotiates; deprecation windows.

### B3.2 Migration Assessment Engine (NEW — top differentiator)
Runs **before** migration; consumes IR + profiling + rules to compute: complexity, est. duration, est. cloud cost, infra requirements, **AI confidence score**, unsupported-feature list, **manual-effort % / automation %**, risk score, business impact, **recommended strategy**. Output = an **Assessment Report** (the primary pre-sales/commercial artifact). Emits `AssessmentCompleted`.

### B3.3 Rule Engine (NEW — foundational for "no core changes")
Config-driven (no code edits) rules for: type mapping, transform mapping, naming conventions, SQL rewriting, business rules, validation policies, security policies, org-specific overrides. **Design:** declarative rule sets (YAML/JSON or DB) with a typed evaluator; org-scoped layering (global → org → project); versioned + auditable. **Hardcoding these is the #1 trap that breaks extensibility — must be config-driven from Phase 1.**

### B3.4 Transformation Library (NEW — IR's vocabulary)
Canonical, target-agnostic transform components the IR speaks and codegen implements: Join, Lookup, Merge, Union, Aggregation, Window, Sort, Filter, Pivot/Unpivot, Hash, Dedup, CDC, **SCD (1/2/3)**, JSON/XML/CSV/Excel/Parquet/Avro handling, API integration. Each has: IR schema + per-target generators + conformance tests. Coverage gaps → flagged by Assessment as manual effort.

### B3.5 Metadata Catalog + Knowledge Graph + Enterprise Search (NEW — foundational)
- **Catalog:** business glossary, data dictionary, technical metadata, lineage, owners, tags, domains, version history, docs.
- **Knowledge Graph:** unified graph linking jobs↔tables↔columns↔pipelines↔transforms↔business-terms↔connectors↔docs↔Jira↔users↔projects. **Powers lineage, impact analysis, and AI context (RAG).** **Store:** start Postgres-backed graph (adjacency + recursive CTEs; optional Apache AGE) behind a `GraphStore` port; Neo4j later if needed — avoid premature graph DB.
- **Enterprise Search:** global search across all entities + logs + reports. Start Postgres FTS / OpenSearch behind a `SearchIndex` port, fed by domain events.

### B3.6 Governance, Compliance & Security-by-default (NEW/extend)
Approval workflows (reuse Temporal signal gate) on deploy/rollback/secret-rotation/admin; change management + version control of artifacts; **policy engine** (e.g. OPA-style) for security/data policies; compliance reporting + frameworks (**GDPR, HIPAA, SOX**); retention policies; full audit (exists, HMAC-chained). Identity: **SSO (SAML/OIDC), MFA/TOTP, external secrets manager (Vault/AWS SM), scoped API keys, session mgmt.**

### B3.7 Observability, Cost Intelligence & SaaS Readiness (NEW)
- **Observability:** centralized logging, metrics, **distributed tracing** (OTEL hooks exist), health + connector + worker + queue monitoring, dashboards (Grafana), alerting, **SLA monitoring**.
- **Cost Intelligence:** estimate cloud infra/storage/compute, **Snowflake credits, Databricks DBUs, AWS/Azure/GCP**, and **projected savings post-modernization**. Feeds Assessment + billing.
- **SaaS readiness:** Org→Department→Team→Project hierarchy; **billing, licensing, subscription plans, quotas, usage analytics** (metered off domain events). Existing `cost_service` extends to billing meters.

### B3.8 Enterprise APIs & AI Specialists & Testing
- **APIs:** REST (exists) + **GraphQL gateway** + CLI + SDK (Python/TS, extend existing) + **webhooks** + **event streaming** + **Terraform provider** + **CI/CD** integrations (run migrations/assessments in pipelines).
- **AI Specialists:** replace single assistant with a **router → domain experts** (Migration Architect, DataStage, SAS, SQL, Snowflake, Databricks, Airflow, Cloud Architect, Troubleshooting, Documentation), each grounded in the **Knowledge Graph (RAG)** + deterministic IR; reuse per-agent provider routing.
- **Visual Workflow Designer:** drag-drop DataStage-like job designer on existing ReactFlow — visual pipelines, dependency viz, live validation, execution preview, breakpoints/debugging, version compare, real-time monitoring (via event stream + SSE).
- **Data Profiling:** null/duplicate/outlier/pattern analysis, quality scoring, column stats, histograms, **PII/sensitive-data detection + classification** (feeds Assessment + Governance).
- **Testing Framework:** unit/integration/regression/performance/load; **synthetic test data + golden datasets**; automated source↔target validation (extends recon).

## B4. Final Architecture Review

**Architectural bottlenecks**
- **IR expressiveness** = central risk: anything IR can't represent breaks deterministic codegen → mitigate with the Transformation Library + AI-assist fallback + Assessment "unsupported feature" reporting (never silent).
- **Knowledge-graph store** could become a bottleneck/over-engineering → port-abstract; Postgres first.
- **Single Temporal cluster / shared workers** → noisy-neighbor at SaaS scale → per-tier task queues, later per-tenant worker pools.

**Scalability limitations** — current single-instance defaults; **data volume must be delegated** to target-native bulk/Spark (engine orchestrates, never streams rows through itself); catalog/IR tables need partitioning + archival.

**Security gaps** — SSO/MFA/secrets-manager/policy-engine (in B3.6); **per-tenant execution isolation** when running customer DB2/Snowflake queries (network seg + sandboxed workers).

**Maintainability** — enforce the pure-core boundary (CI lint); contract/IR/API versioning; one ubiquitous language per context.

**Extensibility** — Rule Engine + Plugin contracts + Transformation Library are the three seams that deliver "new scenarios with no core change." If any is hardcoded, extensibility breaks.

**Performance risks** — large extracts, recon checksums on huge tables (use partition-level hashing), AI latency (cache + async + advisory-only).

**Technical debt to retire** — read-only fat connector ABC; AI-as-engine; metadata-only recon; single-instance assumptions; missing event/observability backbone.

**Commercialization opportunities** — paid **Assessment-as-a-service**; **connector marketplace** revenue share; tiered SaaS (units/connectors/AI usage); **private/enterprise connectors**; on-prem/VPC deployment; certified-partner program; professional services.

**Competitive parity matrix (target)**

| Capability | IBM/Informatica/AWS/DBX/Snowflake | This platform |
|---|---|---|
| Assessment & complexity scoring | ✅ | **Add (B3.2)** — key differentiator with AI |
| Catalog + lineage + impact | ✅ | **Add (B3.5)** |
| Visual designer | ✅ (DataStage/PowerCenter) | **Add (B3.8)** |
| Config rule engine | ✅ | **Add (B3.3)** |
| Multi-cloud cost intelligence | partial | **Add (B3.7)** — differentiator |
| Connector marketplace/SDK | partial | **Add (B3.1)** — differentiator |
| Deterministic + AI-assist convert | ✗ (mostly rules-only) | **Core strength** |
| Governance/compliance | ✅ | **Add (B3.6)** |

## B5. Prioritized Recommendations

**CRITICAL — bake into Phase 0/1 foundation (retrofit is very costly):**
1. **Event-driven backbone** (EventBus port + domain events) — everything else hangs off it.
2. **Versioning everywhere** (IR schema, connector contracts, public API) — backward-compat guarantee.
3. **Rule Engine** (config-driven mappings/policies) — or extensibility is dead on arrival.
4. **Metadata Catalog + Knowledge Graph** (port-abstracted, Postgres-first) — lineage/impact/AI-context substrate.
5. **Pure capability-driven core** + CI guard (no vendor names in `migration_engine/`).
6. **Multi-tenant + security hardening** (Dept/Team/Quota; SSO/MFA/secrets-manager; per-tenant execution isolation).

**HIGH — early phases, after the Phase-1 vertical proves the core:**
7. Migration **Assessment Engine** (+ Data Profiling/PII it depends on). 8. **Transformation Library** (canonical transforms). 9. **Observability** stack (logs/metrics/traces/SLA/alerts). 10. **Connector SDK + Marketplace** contracts. 11. **AI Specialists** (router + KG-RAG). 12. **Enterprise APIs** (GraphQL/webhooks/CLI/SDK) + CI/CD. 13. **Governance/Compliance** workflows + policy engine. 14. **Cost Intelligence**.

**MEDIUM:** 15. **Enterprise Search** (global). 16. **Visual Workflow Designer** (debug/breakpoints). 17. **Testing Framework** (golden/synthetic). 18. **Billing/licensing/plans/usage analytics**. 19. Connector **certification + doc-gen**.

**LOW:** 20. Marketplace monetization/private-connector licensing. 21. Terraform provider. 22. Neo4j/Kafka swap-ins (only if Postgres/Redis hit limits). 23. Advanced designer debugging.

## B6. Revised Roadmap (enterprise primitives folded in)

- **Phase 0 — Enterprise Foundation:** IR (versioned) + canonical types + **Transformation Library skeleton**; **EventBus port + domain events**; connector v2 contracts (versioned) + registry; **Rule Engine**; **Catalog + Knowledge Graph (Postgres-first, port-abstracted)**; DDD module boundaries + CI core-purity lint; new DB models; security hardening kickoff (SSO/MFA/secrets-manager); UI wireframes. *(Most CRITICAL items land here.)*
- **Phase 1 — DB2→Snowflake + Reconciliation (proves the core on real tickets):** as Part A §15, now emitting domain events, driven by the Rule Engine, populating the Catalog/Graph, with a basic **Assessment** + **Data Profiling** pass and **Observability**. Validated on the user's live DB2 + Snowflake.
- **Phase 2 — DataStage ingestion + Visual Designer + AI Specialists:** `.dsx`/`.isx`→IR, job graph, impact analysis, DataStage→Snowflake codegen; designer; KG-grounded AI experts.
- **Phase 3 — Multi-target + Marketplace/SDK:** Databricks/Airflow/S3/file targets from the same IR; Connector SDK + Marketplace; Cost Intelligence; Enterprise APIs (GraphQL/webhooks).
- **Phase 4 — SAS→Databricks + Governance/Compliance + Enterprise Search.**
- **Phase 5 — SaaS commercialization:** billing/licensing/plans/quotas/usage analytics; K8s/Helm + HPA; certification program; scale tests (1000s of units, multi-tenant).

## B7. Product North Star — AI-Driven Migration Velocity (the "why")

The platform exists to **compress migration cycle time** and **multiply productivity** with AI. This makes four things first-class, not optional:

**1. Jira-centric workflow (now CRITICAL, not Phase-5).** Jira is the system of record. Each **MigrationUnit ↔ Jira ticket** (`DPE-####`), two-way sync (status, assignee, comments, time). The platform augments Jira: pull tickets → auto-classify (data vs DataStage vs other) → auto-assess → drive the engine → push artifacts/status/recon results back. Reuse `backend/app/integrations/jira/` (Part A §10); promote to Phase 0/1.

**2. Living Documentation (first-class quality pillar).** Every migration auto-generates and **keeps updated** docs: source→target mapping, transformation logic, lineage, decisions, runbook, rollback steps, recon evidence. **Reuse the existing BMAD doc agent (Paige) + artifact store** (`agents/`), but ground it in the IR + Knowledge Graph so docs are derived from facts (deterministic), AI only narrates. Docs version with the migration and link from Jira.

**3. Validation & Reconciliation (the trust gate that lets teams go fast safely).** Elevated to core engine modules (Part A §6, B3.8): schema validation, row-count, **checksum/hash**, column-stat diffs, sampled-row diffs, PII-aware checks. Recon results are evidence attached to the unit, the docs, and the Jira ticket. *Fast migration is only valuable if recon proves correctness* — so recon is mandatory, automated, and reportable.

**4. Productivity & Velocity Analytics (NEW — how we prove the north star).** A metrics layer fed by domain events that measures: cycle time per unit (created→deployed→reconciled), **automation % vs manual %**, AI-assist acceptance rate, throughput (units/sprint), rework/failure rate, **time saved vs baseline** (calibrated against the user's historical DPE-#### completion times). Surfaced on a **Velocity Dashboard** and in Assessment reports — this is the commercial proof and the internal feedback loop. Ties to B3.2 (Assessment) and B3.7 (Cost Intelligence).

**Priority impact:** Jira sync, Living Docs, and Validation/Recon move into **CRITICAL/Phase-1**; Velocity Analytics is **HIGH** and built on the already-CRITICAL event backbone (B5 #1). "Other migrations" (DB→DB, view, file-interface, schema-change) are handled by the same Any-Source→IR→Any-Target core — no special-casing.

## Updated Verification additions
- **Core-purity test:** CI fails if `migration_engine/` imports any connector/vendor module.
- **Contract-conformance harness:** every connector passes its capability test suite (SDK).
- **Assessment accuracy:** compare engine estimates vs actual on the user's completed real tickets (DPE-####) as a calibration set.
- **Event/observability:** assert domain events emitted + traced for a full Phase-1 run.
