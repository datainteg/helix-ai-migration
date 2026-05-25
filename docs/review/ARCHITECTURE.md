# Helix Migration — Whole-Project Architecture

> Generated 2026-05-26 against `main` at commit `4de7eb0e`.
> Companion file. Per-framework deep reviews live alongside this file:
> [`REVIEW_BACKEND.md`](./REVIEW_BACKEND.md) · [`REVIEW_FRONTEND.md`](./REVIEW_FRONTEND.md) · [`REVIEW_AGENTS_WORKER.md`](./REVIEW_AGENTS_WORKER.md) · [`REVIEW_WEBSITE.md`](./REVIEW_WEBSITE.md) · [`REVIEW_SUMMARY.md`](./REVIEW_SUMMARY.md)

---

## 1. Repository map

```
helix-ai-migration/
├── backend/         # FastAPI HTTP API (~151 files)
├── worker/          # Temporal worker (Python; 9 files)
├── agents/          # AI brain — BMAD + LangGraph + provider adapters (~39 files; shared by backend + worker)
├── connectors/      # Source/target connector adapters (PostgreSQL, MySQL, SQL Server, Snowflake, S3, CSV/Excel + base)
├── _bmad/           # Vendored BMAD-METHOD config + skill files (read by agents/runtime/bmad_loader.py)
├── frontend/        # Next.js 14 product app (~106 files)
├── website/         # Vite + React public marketing site (~41 files)
├── docs/            # Architecture + per-domain reference docs
├── scripts/         # Bootstrap + seed CLI
├── data/            # Local dev artifact + temp output (gitignored)
├── _bmad-output/    # BMAD workflow output (gitignored)
├── docker-compose.yml          # default dev stack
├── docker-compose.dev.yml      # dev override (mounts)
├── docker-compose.build.yml    # production-style images
├── DEPLOY.md, README.md, CONTRIBUTING.md, SECURITY.md
└── .env.example
```

## 2. Stack at a glance

| Layer | Tech |
|---|---|
| HTTP API | FastAPI · SlowAPI rate-limit · OpenTelemetry + Sentry |
| Persistence | PostgreSQL (SQLAlchemy 2 ORM + Alembic) · Redis (rate-limit + JWT denylist) |
| Workflow | Temporal (planning + per-node workflows; signals for human approval) |
| AI brain | BMAD-METHOD framework (vendored) · LangGraph state graph · PydanticAI typed outputs · httpx for vendor APIs |
| LLM adapters | 10 providers — OpenAI, Anthropic, Google Gemini, DeepSeek, OpenRouter, AWS Bedrock, Vertex AI, Azure OpenAI, custom, local |
| Frontend app | Next.js 14 App Router · TypeScript · Tailwind · React Query · Zustand (theme tweaks) · React Flow (mapping canvas) · @dnd-kit (kanban DnD) |
| Public site | Vite · React 18 · TypeScript · Tailwind · React Router 6 · Lucide + Simple Icons |
| Deploy | Docker Compose · single network · static frontend; backend on 8000, frontend on 3000, worker headless, postgres + redis + temporal |

## 3. Request flow (REST)

```
Browser
  ↓ fetch /api/v1/...
FastAPI (backend)
  ├── slowapi rate-limit
  ├── RequestIdMiddleware (correlation id)
  ├── JWT decode → user_id
  ├── resolve_active_org_id() / get_current_organization_id() dependency
  ├── ensure_project_access() guard at route layer
  ├── service layer (org-scoped queries)
  ├── SQLAlchemy session → PostgreSQL
  └── audit chain row (HMAC-linked) on every mutation
        ↓ for workflow-trigger routes
Temporal client.start_workflow(...)
        ↓
Temporal server → Worker (Python)
  ├── activities call agents.runtime.bmad_executor.execute_agent_skill()
  ├── executor → llm_client → provider adapter
  ├── artifact_store writes markdown to _bmad-output/planning-artifacts/
  └── persist_workflow_step_activity uses worker-local SessionLocal
```

## 4. AI brain dataflow

```
Migration requirement (text)
  ↓ HelixBMAD(...).run()  OR  HelixBMAD(...).start_temporal()
LangGraph StateGraph (agents/bmad/graph.py)
  Phase 0  winston_project_context
  Phase 1  mary_analyze
  Phase 2  john_prd → sally_ux
  Phase 3  winston_architecture → winston_stories → winston_readiness
  Phase 4 (gate) approval_gate
            ├── approved → amelia_story → amelia_dev → amelia_qa → amelia_code_review
            ├── rejected → END
            └── pending  → END (resumes via Temporal signal)
  Phase 5  paige_docs

Each node:
  1. read upstream artifacts via artifact_store
  2. build (system, user) prompts from BMAD skill files
  3. call_llm() → provider adapter (OpenAI/Anthropic/...)
  4. PydanticAI / structured_output parses to typed schema
  5. write markdown artifact via artifact_store
```

## 5. Provider adapter registry

```
agents/runtime/providers/
├── base.py              # BaseProvider + CallContext + registry
├── __init__.py          # auto-registers 10 adapters at import
├── openai_provider.py
├── anthropic_provider.py
├── gemini_provider.py
├── deepseek_provider.py (auto-aliases deepseek-chat → v4-flash etc.)
├── openrouter_provider.py
├── bedrock_provider.py  (boto3; 7 model-family body shapes)
├── vertex_provider.py   (google-cloud-aiplatform SDK)
├── azure_provider.py    (AzureOpenAI client; deployment_name)
├── custom_provider.py   (OpenAI-compatible passthrough)
└── local_provider.py    (Ollama / LM Studio)
```

Dispatched via `agents/runtime/llm_client.py:call_llm()` which loads the active `LLMProvider` row, resolves the per-agent mapping (`LLMAgentMapping`), decrypts the secret, and forwards to the registered adapter.

## 6. Data layer

13 SQLAlchemy models grouped by domain:

| Module | Tables |
|---|---|
| `models/identity.py` | organizations, users, roles, permissions, role_permissions, organization_members, password_reset_tokens, org_invitations |
| `models/llm.py` | llm_providers, llm_provider_secrets, llm_agent_mappings |
| `models/project.py` | projects, sub_projects, migration_requirements, source_connections, target_connections, schema_metadata, table_metadata, column_metadata |
| `models/agents.py` | agent_definitions, agent_tasks, agent_outputs, prompt_templates, prompt_versions |
| `models/artifacts.py` | code_artifacts, code_artifact_versions, artifact_dependencies, artifact_lineage, artifact_reviews, artifact_approvals |
| `models/validation.py` | validation_rules, validation_runs, validation_results, recon_runs, recon_results |
| `models/observability.py` | audit_logs (append-only HMAC chain), system_health_checks |
| `models/workflow.py` | workflow_runs, workflow_steps |
| `models/webhook.py` | webhook_endpoints, webhook_deliveries |
| `models/encryption.py` | org_data_encryption_keys |
| `models/sprint.py` | sprints, sprint_tasks, sprint_risks, sprint_approvals, migration_releases, sprint_mapping_nodes, sprint_mapping_edges, sprint_agent_executions, sprint_task_history |

### Migration chain

Alembic single-line chain (each `down_revision` references the prior):

```
25b337c73f7a → 7a5e08bb10ae → b2c3d4e5f6a7 → b2c3d4e5f6a8
  → c3d4e5f6a7b8 → c4d5e6f7a8b9 → d4e5f6a7b8c9 → d5e6f7a8b9c0
  → e5f6a7b8c9d0 → e6f7a8b9c0d1 → f6a7b8c9d0e1 → f7a8b9c0d1e2
  → a1b2c3d4e5f6 (proper column types) → g8h9i0j1k2l3 (connection encrypted_config)
  → h9i0j1k2l3m4 (user_preferences) → i0j1k2l3m4n5 (llm_provider extra_config)
  → j1k2l3m4n5o6 (sprint tables) → k2l3m4n5o6p7 (sprint_task_history)
```

## 7. API surface (18 routers, all under `/api/v1`)

| Router | Mount path | Notes |
|---|---|---|
| auth.py | /auth/* | first-admin, login, logout, refresh, /me, password reset |
| users.py | /users/me/* | profile PATCH, preferences GET/PATCH |
| llm_providers.py | /llm-providers/* | CRUD + key rotation + test_connection + catalogue + models |
| projects.py | /projects/* | + sources, targets, schemas, tables, columns |
| agent_workflows.py | /agent-workflows/*, /projects/{id}/agent-workflows | start + approve + reject + signal-approve/reject + SSE stream |
| sprints.py | /projects/{id}/sprints/*, /sprints/* | 14 endpoints + seed + SSE |
| artifacts.py | /projects/{id}/artifacts*, /artifacts/* | upload + version history |
| code_reviews.py | /artifacts/{id}/{analyze,review} | ad-hoc BMAD review |
| connectors.py | /connectors/* | test, registry, discover, row-count |
| validation.py | /projects/{id}/validation/* | rules + runs + results |
| audit.py | /audit-logs* | append-only chain + verify |
| invitations.py | /invitations/* | invite, accept, revoke |
| webhooks.py | /webhooks/* | + deliveries |
| usage.py | /admin/usage | usage stats |
| superadmin.py | /superadmin/* | platform-level ops |
| encryption.py | /admin/org/rotate-dek | DEK rotation |
| system.py | /system/* | system controls |
| health.py | /health | unauthenticated liveness |

## 8. Frontend route map (Next.js 14)

```
/                            marketing landing redirect
/login
/setup/first-admin           6-step wizard
/dashboard                   Command Center
/projects
/projects/[id]
/projects/[id]/agents        agent canvas
/projects/[id]/developer-workspace
/projects/[id]/sprints/{dashboard, board, mapping, timeline, execution,
                        analytics, dependencies, approval, risks, releases}
/projects/new
/agents
/connectors
/validation
/reconciliation
/developer-workspace, /developer-workspace/[id]
/files, /plugins, /reports, /templates       (placeholder stubs)
/approval
/settings
/admin/{audit-logs, llm-settings, agent-mapping, system-health, users}
```

## 9. Worker

Temporal worker (`worker/main.py`) registers:

- Workflows: `BMADPlanningWorkflow`, `BMADPerNodeWorkflow`
- Activities: `winston_project_context_activity`, `mary_analyze_activity`, `john_prd_activity`, `sally_ux_activity`, `winston_architecture_activity`, `winston_stories_activity`, `winston_readiness_activity`, `amelia_story_activity`, `amelia_dev_activity`, `amelia_qa_activity`, `amelia_code_review_activity`, `paige_docs_activity`, `persist_workflow_step_activity`

Worker has its own SessionLocal (`worker/db/session.py`) — does not import `app.db.session` (GAP 8 fix). Persists workflow steps directly via `WorkflowStep` model.

## 10. Public website

Vite + React static site, separately deployable. Routes:

```
/              landing (Hero, Features, FeatureMap, Architecture, Agents,
               Connectors, ValidationRecon, DeveloperWorkspace, Sprint teaser,
               Docker install, Roadmap, CTA)
/features
/architecture
/docs          21 categories, content-driven from docs-content.ts
/open-source
```

View Demo CTA opens `/helix-console-demo.html` (1.5 MB Figma export) in a new tab. Build to `dist/` for any static host. `npm run build:hostinger` additionally copies `.htaccess` for Apache/LiteSpeed deploys.

## 11. Security model summary

- **Cross-tenant:** every entry point either (a) uses `Depends(get_current_organization_id)` or (b) calls `resolve_active_org_id(db, user_id)`. Suspended members get 403 uniformly.
- **JWT:** access tokens decoded in `app.auth.jwt`. Redis denylist for revoked tokens. SSE endpoint accepts JWT via `?token=` query string (EventSource limitation; same org scope enforced).
- **Encryption:** Fernet for LLM API keys + connector configs + webhook secrets. Per-org DEK supported (admin/org/rotate-dek).
- **Audit chain:** append-only `audit_logs` table with HMAC entry_hash chained to previous row. Visible tamper if any row is mutated.
- **Rate limit:** SlowAPI per-IP + per-route limits on auth, password reset, connector test, etc.
- **SSRF:** connector discovery endpoints validate that the resolved host is not RFC1918 / loopback / link-local / cloud-metadata, unless `HELIX_ALLOW_PRIVATE_HOSTS=1` is set on the backend (on-prem DBs need it).
- **Secrets:** never returned in any API response; UI receives only `api_key_masked` / `config_masked`.

## 12. Known crossover seams

| Concern | Where it lives |
|---|---|
| Shared schema (cross-package) | `app.models.workflow.WorkflowStep` imported by worker activity — only remaining cross-package model dep |
| Correlation id propagation | RequestIdMiddleware → workflow_service.start_bmad_planning_workflow → HelixBMAD constructor → activity input_data → executor → artifact frontmatter |
| Token budget | bmad_executor truncates SKILL.md + upstream artifacts head + tail before sending to LLM |
| Live execution | SSE: `GET /api/v1/projects/{id}/sprints/executions/stream?token=` pushes 2s snapshots; auto-closes at 5min |

## 13. Where to read what

| Question | File |
|---|---|
| How is the request authed? | `backend/app/auth/{jwt.py, dependencies.py}` |
| How is the org scope enforced? | `backend/app/auth/dependencies.py::resolve_active_org_id` |
| How does a BMAD workflow start? | `backend/app/services/workflow_service.py` → `HelixBMAD` |
| How does a node execute? | `agents/runtime/bmad_executor.py` |
| How are skills loaded? | `agents/runtime/bmad_loader.py` |
| How are LLMs called? | `agents/runtime/llm_client.py` → `providers/*.py` |
| How is an artifact stored? | `agents/runtime/artifact_store.py` |
| How does Temporal run nodes? | `worker/workflows/bmad_per_node_workflow.py` |
| How does the worker talk to the DB? | `worker/db/session.py` (decoupled from backend) |
| How does a sprint get seeded? | `backend/app/services/sprint_seed.py` (HTTP) / `scripts/seed.py` (CLI) |

---

> Per-framework deep reviews follow. Each is a separate file in this folder.
