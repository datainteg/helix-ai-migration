# Helix Migration

**Open-source AI-powered migration and validation platform.** Self-hosted, multi-agent migration planning with human approval gates.

> **Status:** MVP foundation complete. Several capabilities are stubs or returning canned data — see [Honest Capability Matrix](#honest-capability-matrix) before evaluating for production use.
>
> **GitHub:** `https://github.com/datainteg/helix-ai-migration`
> **Website:** `https://helix.datainteg.io`
> **Docker Images:** `datainteg/helix-ai-migration-{frontend,backend,worker}`

---

## What Helix Migration Is

Helix Migration is a self-hosted migration command center. It coordinates AI agents that produce structured migration plans, captures source-and-target metadata, manages artifact uploads with safe storage, and orchestrates approvals — all through a typed FastAPI backend, a Next.js frontend, and Temporal-backed durable workflows.

It is intentionally **not** a one-click migration tool. AI outputs are drafts. Human approval is required before any generated artifact is treated as production-ready.

## What Helix Migration Is Not (Yet)

Be explicit about gaps. As of 2026-05-23 the following capabilities are stubbed or partial:

- **BMAD agents do not yet call real LLMs.** The 4 wired LangGraph nodes (BA, Architect, Validation Planner, Approval Gate) return hardcoded Pydantic-validated outputs based on the BMAD agent metadata, not LLM responses. The infrastructure (`agents.runtime.llm_router.route_llm_call`) exists; the nodes have not been wired through it.
- **Validation and reconciliation API endpoints return placeholder data.** `POST /validation-runs` and `POST /recon-runs` create a row with `status="completed"` and a hardcoded summary. The frontend validation/reconciliation pages render fixture data, not API results. A working row-count reconciliation service exists in `backend/app/services/recon_service.py` but is not yet wired into the API.
- **Only 3 of 8 connectors are functional.** PostgreSQL, CSV, and Excel work. MySQL, SQL Server, Snowflake, S3 are skeletons returning `not implemented yet` and empty lists.
- **The Temporal worker container does not build cleanly.** `worker/Dockerfile` is missing the `pip install -r requirements.txt` step. In dev the path is exercised via `local_fallback`; production builds need this fix before Temporal is usable.
- **Workflow approval endpoint does not persist the decision.** `POST /agent-workflows/{id}/approve` returns `{"status": "recorded"}` but does not update `WorkflowRun.status` or write an `ArtifactApproval` row.
- **No rate limiting.** Auth, connector test, and LLM test endpoints accept unlimited attempts.
- **Frontend `useApi()` hook exists but is unused.** Every page hand-rolls its own `fetch` calls.

See [ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md) for the full review with line-level citations and [FUTURE_IMPROVEMENTS.md](FUTURE_IMPROVEMENTS.md) for the prioritized plan to close these gaps.

---

## Quickstart

### Docker (recommended)

```bash
git clone https://github.com/datainteg/helix-ai-migration.git
cd helix-ai-migration
cp .env.example .env
# Edit .env — set JWT_SECRET_KEY and ENCRYPTION_KEY to non-default values
docker compose -f docker-compose.dev.yml up -d
# Frontend: http://localhost:8080
# Backend:  http://localhost:8000   (Swagger: /docs)
# Temporal UI: http://localhost:8233
```

> ⚠️ **Known issue:** The worker container will currently fail to import `temporalio` because the worker `Dockerfile` does not install its `requirements.txt`. In dev, the backend falls back to `local_fallback` mode (runs BMAD graph in-process) and still works end-to-end. To fix the worker image, see [FUTURE_IMPROVEMENTS.md → C-1](FUTURE_IMPROVEMENTS.md#c-1-fix-worker-dockerfile).

### Local development (no Docker)

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload      # http://localhost:8000

# Worker (Temporal optional; backend falls back automatically)
cd worker
pip install -r requirements.txt
python main.py

# Frontend
cd frontend
npm install
npm run dev                        # http://localhost:3000
```

### First-time setup

1. Open `http://localhost:3000` (or `:8080` on Docker).
2. Click **Setup First Admin** and create the bootstrap user + organization.
3. Log in. Add an LLM provider under **Admin → LLM Settings** (key is Fernet-encrypted; masked on display).
4. Create a project, add a requirement, click **Generate Migration Plan**.

---

## Honest Capability Matrix

| Capability | Status | Notes |
|---|---|---|
| **Authentication** (JWT + bcrypt) | ✅ Working | HS256, 60-min tokens, `localStorage` storage on frontend. No refresh, no revocation. |
| **First admin bootstrap** | ✅ Working | Idempotent — second call returns 400. |
| **Organization isolation** | ✅ Working | All major resources scoped by `organization_id`. Cross-org returns 404. |
| **RBAC** | ✅ Working | 7 roles, 17 permissions; `require_permission()` / `require_admin` decorators. |
| **LLM provider CRUD** | ✅ Working | 7 provider types modeled. Only OpenAI-compatible `test_connection` is implemented; Anthropic/Gemini/Local return `not implemented yet`. |
| **API key encryption + masking** | ✅ Working | Fernet via `secret_service.py`; never returned in full. |
| **Project / requirement CRUD** | ✅ Working | Note: `migration_type` sent by UI is silently dropped by backend schema. |
| **Artifact upload (.py/.sql)** | ✅ Working | 25 MB cap, type allowlist, UUID storage names, path-traversal guarded. |
| **Artifact analyze / code review API** | 🟡 Partial | Calls LLM if a provider is configured; falls back to static checks otherwise. Cross-org provider leak in fallback resolution (see ARCHITECTURE_REVIEW.md C-3). |
| **Code Review UI** | 🟡 Partial | Frontend expects fields (`inputs_detected`, `quality_score`, `migration_suggestions`, etc.) that the backend does not return — display will be empty until contract is aligned. |
| **BMAD planning workflow (LangGraph)** | 🟡 Partial | 4-node graph runs end-to-end with structured outputs, but outputs are hardcoded text, not LLM-generated. |
| **BMAD registered agents** | ℹ️ Metadata only | 13 agents in `official_agents.py`; 4 wired into the graph; the rest are reference metadata. |
| **Temporal workflow integration** | 🟡 Partial | Workflow + activity + worker code is correct; worker Docker image is broken; backend uses `local_fallback` in dev. |
| **Workflow persistence** | ✅ Working | `WorkflowRun` + `WorkflowStep` rows written via `_persist_workflow_result`. |
| **Workflow approval endpoint** | 🔴 Stub | Returns success without updating any row. |
| **Validation engine API** | 🔴 Stub | Returns hardcoded `status="completed"`. |
| **Reconciliation engine API** | 🔴 Stub | API hardcodes `"Source: 150000 rows, Target: 149998 rows. Difference: 2"`. A real row-count comparison exists in `recon_service.run_row_count_recon` but is not called by any endpoint. |
| **Validation / Reconciliation UI** | 🔴 Stub | Hardcoded fixtures in the page components, not from API. |
| **PostgreSQL connector** | ✅ Working | Schema, table, column, row-count discovery. ⚠️ Password not URL-encoded. |
| **CSV / Excel connectors** | ✅ Working | pandas-backed; loads entire file for row count. |
| **MySQL / SQL Server / Snowflake / S3 connectors** | 🔴 Stub | Return `not implemented yet` + empty lists. |
| **Connector framework (base class, registry, identifier validation)** | ✅ Working | Strict identifier whitelist `^[A-Za-z_][A-Za-z0-9_]*$`. Custom connector registry available. |
| **Audit logs** | 🟡 Partial | Written for first-admin and LLM provider CRUD only; most state-changing endpoints do not audit. |
| **System health endpoint** | 🟡 Partial | Reports database; Redis / Temporal / Worker report `"unknown"` — no actual probe. |
| **Frontend dashboard metrics** | 🔴 Stub | Hardcoded `0` for all counters. |
| **Agent workflow canvas (`/projects/{id}/agents`)** | 🔴 Stub | Hardcoded 6-node mockup; not connected to real workflow state. |
| **Developer workspace nested page (`/projects/{id}/developer-workspace`)** | 🔴 Stub | Static three-column layout with placeholder text. |
| **Rate limiting** | 🔴 Missing | Redis provisioned but unused. |
| **Structured logging / tracing / metrics** | 🔴 Missing | Plain text logs; no correlation IDs, no Prometheus endpoint, no Sentry. |
| **CI/CD pipelines** | 🔴 Missing | No `.github/workflows/`. |

Legend: ✅ working · 🟡 partial · 🔴 stub or missing · ℹ️ informational

---

## Architecture

```
Browser
  │
  ▼
Next.js (15 pages, TS, Tailwind)             [frontend/]
  │  JWT bearer
  ▼
FastAPI (13 routers, 10 services, 10 models) [backend/app/]
  ├── Auth: JWT + bcrypt + RBAC
  ├── Org-scoped CRUD: projects, providers, artifacts, …
  ├── Audit + system health
  └── Workflow service ──┐
                         │
                  ┌──────┴───────┐
                  ▼              ▼
            Temporal client   local_fallback
            (helix-bmad-task   (run_bmad_graph
             -queue)            in-process)
                  │              │
                  ▼              ▼
          Worker ───► Activity ───► LangGraph (BA → Architect → VP → Approval)
          [worker/]               [agents/bmad/]
                                       │
                                       └─► route_llm_call (mock by default)
                                                   │
                                                   └─► LLM Provider Adapters
                                                       [backend/app/services/llm_provider_adapters.py]

PostgreSQL (7 Alembic migrations)            [backend/alembic/versions/]
  organizations, users, roles, permissions, role_permissions,
  organization_members, projects, subprojects, migration_requirements,
  source_connections, target_connections, schemas, tables, columns,
  llm_providers, llm_provider_secrets, llm_agent_mappings,
  agent_definitions, agent_tasks, agent_outputs,
  prompt_templates, prompt_versions,
  code_artifacts, code_artifact_versions, artifact_dependencies,
  artifact_lineage, code_reviews, artifact_approvals,
  validation_rules, validation_runs, validation_results,
  recon_runs, recon_results,
  workflow_runs, workflow_steps,
  audit_logs, system_health_checks
```

Detailed architecture: [ARCHITECTURE.md](ARCHITECTURE.md). Database schema: [DATABASE_DESIGN.md](DATABASE_DESIGN.md). API surface: [API_DESIGN.md](API_DESIGN.md). Agent workflow: [AGENT_WORKFLOW.md](AGENT_WORKFLOW.md).

---

## Tech Stack (Actual, Not Aspirational)

### Frontend ([frontend/package.json](frontend/package.json))

| In `package.json` | Status |
|---|---|
| `next@^14.2.0`, `react@^18.3.0`, TypeScript | ✅ |
| Tailwind CSS, PostCSS, autoprefixer | ✅ |
| `lucide-react`, `clsx`, `class-variance-authority`, `tailwind-merge` | ✅ shadcn primitives present; full shadcn/ui components not installed |
| **TanStack Query** | ❌ not installed |
| **Zustand** | ❌ not installed |
| **React Flow** | ❌ not installed (agent canvas page is a hand-coded mockup) |
| **Framer Motion** | ❌ not installed |

### Backend ([backend/requirements.txt](backend/requirements.txt))

| Pinned | Purpose |
|---|---|
| `fastapi>=0.115.0`, `uvicorn[standard]>=0.30.0` | API |
| `pydantic>=2.0.0`, `pydantic-settings>=2.0.0`, `email-validator>=2.0.0` | Schemas |
| `sqlalchemy>=2.0.0`, `alembic>=1.13.0`, `psycopg2-binary>=2.9.0` | DB |
| `redis>=5.0.0` | Provisioned, unused by code |
| `python-jose[cryptography]>=3.3.0`, `passlib[bcrypt]>=1.7.0` | JWT + bcrypt |
| `python-multipart>=0.0.9` | Uploads |
| `httpx>=0.27.0` | LLM provider calls + tests |
| `langgraph>=0.2.0` | BMAD StateGraph |
| `pytest>=8.0.0`, `pytest-asyncio>=0.23.0` | Tests |

### Worker ([worker/requirements.txt](worker/requirements.txt))

| Pinned | Purpose |
|---|---|
| `temporalio>=1.8.0` | Temporal worker SDK |

> ⚠️ `worker/Dockerfile` does not currently install this. See [FUTURE_IMPROVEMENTS.md → C-1](FUTURE_IMPROVEMENTS.md#c-1-fix-worker-dockerfile).

### Storage

- Metadata: PostgreSQL (or SQLite for tests, via `app.db.session`)
- Artifacts: local filesystem under `ARTIFACT_STORAGE_PATH` (default `./data/artifacts`)
- Cache / rate-limit: Redis (provisioned, not yet used)

---

## Repository Layout

```
helix-ai-migration/
├── backend/
│   ├── app/
│   │   ├── api/                # 13 routers
│   │   ├── auth/               # jwt, dependencies, RBAC
│   │   ├── core/config.py      # Pydantic settings
│   │   ├── db/session.py       # SQLAlchemy engine + Base
│   │   ├── models/             # 9 model files
│   │   ├── schemas/            # 5 Pydantic schema files
│   │   ├── services/           # 10 services (auth, workflow, llm, recon, …)
│   │   ├── storage/local.py    # Safe artifact storage
│   │   └── main.py             # FastAPI app + middleware
│   ├── alembic/versions/       # 7 migrations
│   ├── tests/                  # 15 test files, 60 tests (58 pass / 2 skip)
│   └── requirements.txt
├── agents/
│   ├── bmad/                   # graph, nodes, schemas, state, official_agents
│   ├── runtime/                # llm_router, structured_output, types
│   ├── code_analyzer_agent/    # analyzer.py (LLM + static fallback)
│   ├── code_review_agent/      # reviewer.py
│   ├── schemas/                # developer_agents.py
│   └── bmad/BMAD-METHOD/       # Vendored upstream BMAD-METHOD project
├── connectors/
│   ├── base/                   # BaseConnector, identifiers, exceptions
│   ├── postgres/               # ✅ functional
│   ├── files/                  # ✅ csv + excel functional
│   ├── mysql/                  # 🔴 skeleton
│   ├── sqlserver/              # 🔴 skeleton
│   ├── snowflake/              # 🔴 skeleton
│   ├── s3/                     # 🔴 skeleton
│   └── custom/registry.py
├── worker/
│   ├── workflows/bmad_planning_workflow.py
│   ├── activities/bmad_activities.py
│   ├── main.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/                # 17 page routes (Next.js App Router)
│   │   ├── features/developer-workspace/   # ApprovalModal, DiffViewer, VersionHistoryDrawer
│   │   ├── lib/                # auth-context, api/client, use-api
│   │   └── app/globals.css
│   ├── package.json
│   └── Dockerfile              # Multi-stage Node 20 alpine
├── docs/                       # 19 subdirectories of further documentation
├── ARCHITECTURE.md, AGENT_WORKFLOW.md, API_DESIGN.md, DATABASE_DESIGN.md,
├── SECURITY.md, DOCKER_GUIDE.md, DEVELOPMENT.md, TESTING.md, ROADMAP.md,
├── CONTRIBUTING.md, AGENTS.md, UI_UX_GUIDE.md, TRACKING.md,
├── CODE_REVIEW.md             # File-to-prompt audit
├── IMPROVEMENTS.md            # Line-by-line review
├── ARCHITECTURE_REVIEW.md     # Full system review (this codebase)
├── FUTURE_IMPROVEMENTS.md     # Prioritized engineering plan
├── docker-compose.dev.yml     # 7 services for dev
├── docker-compose.yml         # Production compose (uses published images)
└── .env.example
```

---

## API Surface (Implemented)

All routes are prefixed `/api/v1`. Generated OpenAPI: `http://localhost:8000/docs`.

### Auth
- `POST /auth/first-admin` — bootstrap (one-shot)
- `POST /auth/login`
- `GET /auth/me`

### Projects + metadata
- `POST GET /projects`, `GET /projects/{id}`
- `POST /projects/{id}/subprojects`
- `POST /projects/{id}/requirements`
- `POST GET /projects/{id}/sources`, `POST GET /projects/{id}/targets`
- `POST /projects/{id}/schemas`, `POST /schemas/{id}/tables`, `POST /tables/{id}/columns`

### LLM providers
- `GET POST /llm-providers`, `GET PATCH DELETE /llm-providers/{id}`
- `POST /llm-providers/{id}/rotate-key`, `POST /llm-providers/{id}/test`
- `GET POST /llm-agent-mappings`

### Agent tasks + workflows
- `POST GET /projects/{id}/agent-tasks`, `POST GET /agent-tasks/{id}/outputs`
- `POST GET /prompt-templates`, `POST /prompt-templates/{id}/versions`
- `POST /projects/{id}/agent-workflows` — start BMAD planning
- `GET /agent-workflows/{id}` — status
- `POST /agent-workflows/{id}/approve` — **stub: no persistence**

### Artifacts + code review
- `POST /projects/{id}/artifacts/upload`
- `GET /projects/{id}/artifacts`, `GET /artifacts/{id}`, `GET /artifacts/{id}/versions`
- `POST /artifacts/{id}/analyze`, `POST /artifacts/{id}/review`
- `POST /artifacts/{id}/convert` — **stub: writes fake content_hash, unsafe storage path**
- `POST /artifact-versions/{id}/approve`, `POST /artifact-versions/{id}/reject`
- `GET /code-reviews/{id}`

### Validation + reconciliation
- `POST GET /projects/{id}/validation-rules`
- `POST /projects/{id}/validation-runs` — **stub: returns `status="completed"` with no checks executed**
- `POST /projects/{id}/recon-runs` — **stub: returns hardcoded `150000/149998`**

### Connectors
- `POST /connectors/test`, `GET /connectors/registry`
- `POST /connectors/discover/{schemas|tables|columns}`
- `POST /connectors/row-count`

### Observability
- `GET /audit-logs` (requires `admin:audit:read`)
- `GET /system/health` (admin), `GET /system/workers`, `GET /system/failed-jobs`
- `GET /health` (unauthenticated)

---

## Security

What is implemented today:

- **JWT (HS256) + bcrypt** for authentication; `Bearer` tokens on all protected endpoints.
- **Fernet-encrypted LLM provider keys**; masked on display.
- **Path-traversal-proof artifact storage** with allowlisted file types and 25 MB size cap.
- **SQL identifier whitelist** (`^[A-Za-z_][A-Za-z0-9_]*$`) for any user-supplied schema/table/column names hitting a connector.
- **Organization isolation** on all major resources; cross-org access returns 404.
- **RBAC** with 7 roles and 17 permissions.
- **Production guardrails** in `Settings.model_post_init` — refuses to boot with default `JWT_SECRET_KEY` / `ENCRYPTION_KEY` / `APP_SECRET_KEY` when `APP_ENV=production`.

What is **not** yet implemented (do not deploy to production without these):

- Rate limiting on any endpoint (auth, connector-test, and LLM-test are particularly exposed).
- JWT revocation / token blacklist.
- Password strength validation.
- SSL/TLS enforcement on connector connections.
- URL-encoding of credentials in connector connection strings.
- Audit logging on most state-changing endpoints.
- SSRF protection on LLM-provider `base_url` and connector-test request bodies.
- Per-organization data encryption keys (DEK/KEK envelope).
- Strong `ENCRYPTION_KEY` validation (currently any string is SHA-256-derived into a Fernet key).

See [SECURITY.md](SECURITY.md) for the security model and [ARCHITECTURE_REVIEW.md § 14](ARCHITECTURE_REVIEW.md) for threat-model details.

---

## Testing

```bash
cd backend
pytest tests/ -v
# 60 tests total, 58 pass, 2 skipped (Temporal integration tests requiring live server)
```

Coverage highlights:

- `test_structured_output.py` — 30 tests for JSON extraction + Pydantic validation
- `test_auth.py` — full auth flow, cross-org denial, RBAC denial
- `test_temporal_worker.py` — 8 unit tests; 2 integration skipped without Temporal server
- `test_connectors.py` — base class, identifier validation, custom registry, Postgres mock, CSV + Excel functional
- `test_workflow.py` — BMAD graph + persistence
- `test_upload.py` — filename sanitization + path safety

What is **not** covered:

- Frontend (zero tests — no Playwright, no Vitest config)
- Validation / reconciliation execution paths (because they are stubs)
- Connector adversarial inputs (SQL injection mutations of `validate_identifier`)
- Per-org DEK encryption (because it does not exist yet)
- E2E flows through the UI

See [TESTING.md](TESTING.md).

---

## Documentation Index

| Document | Purpose |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture overview |
| [AGENT_WORKFLOW.md](AGENT_WORKFLOW.md) | BMAD + LangGraph design |
| [API_DESIGN.md](API_DESIGN.md) | REST conventions |
| [DATABASE_DESIGN.md](DATABASE_DESIGN.md) | Schema and migration strategy |
| [DOCKER_GUIDE.md](DOCKER_GUIDE.md) | Container layout |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Local setup |
| [SECURITY.md](SECURITY.md) | Security model + planned hardening |
| [TESTING.md](TESTING.md) | Test strategy |
| [ROADMAP.md](ROADMAP.md) | Phase plan with corrected status |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute |
| [CODE_REVIEW.md](CODE_REVIEW.md) | File-to-prompt audit |
| [IMPROVEMENTS.md](IMPROVEMENTS.md) | Line-by-line review findings |
| **[ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md)** | **Full architectural review with criticals + corrections** |
| **[FUTURE_IMPROVEMENTS.md](FUTURE_IMPROVEMENTS.md)** | **Prioritized engineering plan** |

---

## Project Identity

| Item | Value |
|---|---|
| Product | Helix Migration |
| Repository | `helix-ai-migration` |
| Website | `helix.datainteg.io` |
| Frontend image | `datainteg/helix-ai-migration-frontend` |
| Backend image | `datainteg/helix-ai-migration-backend` |
| Worker image | `datainteg/helix-ai-migration-worker` |
| License | See [LICENSE](LICENSE) |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Good first issues are tagged in the GitHub repo. The single highest-impact contributions today are:

1. **Wire BMAD nodes through `agents.runtime.llm_router.route_llm_call`** — uses existing infrastructure, eliminates the "hardcoded text" problem, and gives the platform a real first AI capability.
2. **Replace the stub validation/reconciliation endpoints** by calling `recon_service.run_row_count_recon` (already implemented) and exposing schema-compare via `connector_service.discover_columns`.
3. **Fix `worker/Dockerfile`** so Temporal works in containers (one line).
4. **Implement the four stub database connectors** (MySQL, SQL Server, Snowflake, S3) following the working PostgreSQL pattern.
5. **Frontend `useApi()` adoption** + `<Card>` / `<EmptyState>` extraction.

---

## License

Open-source — see [LICENSE](LICENSE).
