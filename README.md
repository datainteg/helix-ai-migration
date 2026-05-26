# Helix Migration

**Open-source AI-powered data migration + validation platform.** Six BMAD-METHOD
agents (Mary, Paige, John, Sally, Winston, Amelia) collaborate on a 13-step
pipeline to plan, design, build, validate, and document data migrations —
Salesforce → Snowflake, Oracle → Databricks, SQL Server → Snowflake, and more.

> **Self-hosted.** Clone the repo, run `./setup.sh`, configure an LLM
> provider, submit a migration requirement, and watch the 13-node BMAD
> pipeline produce real markdown artifacts you can review, approve, and ship.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

---

## 1-command install

```bash
git clone https://github.com/datainteg/helix-ai-migration.git \
  && cd helix-ai-migration \
  && ./setup.sh --non-interactive \
       --domain helix.example.com \
       --admin-email ops@example.com
```

Or use the CLI to install from anywhere after cloning:

```bash
pipx install helix-cli
helix install --domain helix.example.com --admin-email ops@example.com
```

After the stack is up, open `https://helix.example.com/setup/first-admin`
(or `http://localhost:3000/setup/first-admin` for local dev).

---

## What it does

Helix turns a one-line migration requirement ("migrate Salesforce CRM customer
+ order tables to Snowflake with row-level recon") into a complete, reviewable
migration plan:

1. **Mary** (Business Analyst) writes a product brief.
2. **John** (Product Manager) drafts the PRD.
3. **Sally** (UX Designer) plans the operator UX.
4. **Winston** (System Architect) produces architecture + epics + stories +
   a readiness check.
5. **Human approval gate** — you review the plan before any implementation
   work starts.
6. **Amelia** (Senior Engineer) creates the dev story, implements the code,
   generates E2E tests, and runs an adversarial code review.
7. **Paige** (Tech Writer) writes the migration docs.

Every step writes a real markdown artifact. Downstream agents read upstream
artifacts as context. Human approval is delivered via a Temporal signal —
the workflow durably waits up to 48 hours and resumes when you click Approve.

---

## What's new in v0.3.0

| Area | Change |
|------|--------|
| **Pagination envelope** | All list endpoints now return `{items, total, limit, offset}`. SDKs unwrap transparently. |
| **DEK rotation** | `POST /admin/org/rotate-dek` — zero-downtime re-wrap of org encryption keys. |
| **A11Y AA** | 44 Next.js routes now carry `metadata.title`; modal primitive refactored for focus-trap. |
| **Caddy TLS** | Recommended reverse-proxy config added to `DEPLOY.md`; SSE buffering handled automatically. |
| **Slack permission gate** | Webhook delivery gated by org-scoped Slack permission; signing-secret validation. |
| **Compliance PDF** | Audit chain + validation + recon + cutover artifacts exportable as one PDF per project. |
| **Schema drift watcher** | Real-time drift detection between source/target schema snapshots. |
| **Knowledge base** | RAG document upload + keyword search (vector embeddings pending). |
| **Marketplace** | 7 built-in plugins + custom connector registry. |
| **Replay / pair-review / rollback** | `POST /workflows/{id}/replay`, `POST /artifacts/{id}/pair-review`, `POST /artifacts/{id}/rollback-generate`. |

See [docs/ROADMAP.md](docs/ROADMAP.md) for the full roadmap.

---

## Stack

- **Backend:** FastAPI + PostgreSQL + Redis + SQLAlchemy + Alembic + Pydantic
- **Workflow engine:** Temporal (durable retries, signals, queries)
- **AI brain:** [BMAD-METHOD](https://github.com/datainteg/BMAD-METHOD) (vendored)
  + LangGraph (state graph) + PydanticAI (typed LLM transport) + httpx (fallback)
- **Frontend:** Next.js 14 (App Router) + TypeScript + Tailwind + React Query + Zustand
- **Deploy:** Docker Compose + optional Caddy for TLS, single network, no Kubernetes required

---

## Quick start (≈ 5 minutes, local dev)

```bash
git clone https://github.com/datainteg/helix-ai-migration.git
cd helix-ai-migration

# Generate strong secrets into .env
./scripts/generate-secrets.sh           # Linux / macOS / WSL
.\scripts\generate-secrets.ps1          # Windows PowerShell

# Build images locally
docker compose -f docker-compose.yml -f docker-compose.build.yml build

# Start the stack (Postgres, Redis, Temporal, backend, worker, frontend)
docker compose up -d

# Open http://localhost:3000/setup/first-admin → add LLM provider → submit migration
```

Full deployment guide: [DEPLOY.md](DEPLOY.md).

---

## SDK & CLI (v0.2.0+)

Install:

```bash
pip install helix-cli          # or: pipx install helix-cli
pip install helix-sdk          # Python SDK
npm install @helix/sdk         # TypeScript SDK (types included)
```

Common CLI commands:

```bash
helix login --api https://helix.example.com --email you@org.com
helix projects list
helix projects new --name "Oracle GL → Snowflake"
helix workflow start --project <id> --requirement-id <req>
helix workflow status <workflow-id>
helix cost summary --days 30
helix templates list
helix cutover list --project <id>

# Headless first-admin (CI / scripted installs):
helix admin bootstrap \
  --api https://helix.example.com \
  --email ops@example.com \
  --password-stdin \
  --org-name "Acme Corp" \
  --accept-tos
```

**Breaking change (v0.2.0):** all list endpoints now return a pagination
envelope `{items, total, limit, offset}`. Python/TypeScript SDKs unwrap
transparently via `.list()` (back-compat bare array) and `.paginated()`
(new).

---

## Repo layout

```
helix-ai-migration/
├── agents/                  # AI brain (HelixBMAD class)
│   ├── helix.py             # Top-level class facade
│   ├── bmad/                # LangGraph wiring + Pydantic schemas
│   │   └── BMAD-METHOD/     # Vendored BMAD framework (read-only)
│   ├── runtime/             # BMAD loader, artifact store, executor, LLM transports
│   └── tests/               # 28 unit + integration tests
├── _bmad/                   # BMAD installer config + scripts
├── backend/                 # FastAPI app (18 routers, 18 services, 28+ migrations)
├── worker/                  # Temporal worker (13-node per-node + monolithic workflows)
├── connectors/              # 7 built-in source/target connectors + custom registry
├── frontend/                # Next.js 14 App Router
├── cli/                     # helix-cli Python package
├── scripts/                 # generate-secrets.{sh,ps1}
├── docker-compose.yml       # Primary stack
├── docker-compose.build.yml # Build overlay
├── docker-compose.dev.yml   # Dev overrides (hot reload, exposed ports)
├── DEPLOY.md                # Deployment guide
└── docs/                    # Architecture, roadmap, guides
```

---

## The 13-node BMAD pipeline

| # | Node | Agent | Skill | Phase |
|---|------|-------|-------|-------|
| 1 | winston_project_context | Winston | bmad-generate-project-context | 0 — shared memory |
| 2 | mary_analyze | Mary | bmad-product-brief | 1 — Analysis |
| 3 | john_prd | John | bmad-prd | 2 — Planning |
| 4 | sally_ux | Sally | bmad-create-ux-design | 2 — Planning |
| 5 | winston_architecture | Winston | bmad-create-architecture | 3 — Solutioning |
| 6 | winston_stories | Winston | bmad-create-epics-and-stories | 3 |
| 7 | winston_readiness | Winston | bmad-check-implementation-readiness | 3 |
| — | approval_gate | human | conditional signal | gate |
| 8 | amelia_story | Amelia | bmad-create-story | 4 — Implementation |
| 9 | amelia_dev | Amelia | bmad-dev-story | 4 |
| 10 | amelia_qa | Amelia | bmad-qa-generate-e2e-tests | 4 |
| 11 | amelia_code_review | Amelia | bmad-code-review | 4 |
| 12 | paige_docs | Paige | bmad-document-project | 5 — Docs |

Conditional branching after the approval gate:
- `approved` → continues through implementation phase
- `rejected` → ends with status=rejected
- `None` → pauses (status=pending), resumable

Wave-2 additions: endpoints for replay (`POST /workflows/{id}/replay`),
pair-review (`POST /artifacts/{id}/pair-review`), and rollback
(`POST /artifacts/{id}/rollback-generate`).

---

## How agents communicate

Agents talk via **markdown artifacts** written to a shared directory —
exactly how BMAD-METHOD intends:

- **Per-agent artifacts:** `_bmad-output/planning-artifacts/{project_id}/{agent_code}/{timestamp}-{slug}.md`
- **Shared memory:** `project-context.md` (created by Phase 0) is loaded by
  every agent via their `customize.toml:persistent_facts` glob.

Each artifact has YAML frontmatter (Pydantic-validated metadata) + free-form
markdown body (the deliverable). Downstream agents read prior artifacts via
`agents.runtime.artifact_store.collect_prior_context()`.

---

## LLM provider support

Configure providers + per-agent model routing via the admin UI. Supported:

- OpenAI (GPT-4.1, GPT-4o, o1, o3-mini)
- Anthropic (Claude Opus / Sonnet / Haiku)
- Google Gemini (2.0 Flash, 1.5 Pro)
- DeepSeek (V3, R1, Coder)
- OpenRouter (any model)
- Custom OpenAI-compatible endpoint
- Local Ollama / LM Studio

Each of the 6 BMAD agents can run on a different model. Cheap model for Mary,
strong model for Winston, fast model for Amelia.

---

## Built-in connectors

| Connector | Read | Write | Schema | Row count | Notes |
|-----------|------|-------|--------|-----------|-------|
| PostgreSQL | ✅ | ✅ | ✅ | ✅ | psycopg2 |
| MySQL | ✅ | ✅ | ✅ | ✅ | pymysql, SSL default-on |
| SQL Server | ✅ | ✅ | ✅ | ✅ | pyodbc, ODBC 18 |
| Snowflake | ✅ | ✅ | ✅ | ✅ | snowflake-sqlalchemy |
| Amazon S3 | ✅ | — | List buckets | — | boto3, STS supported |
| CSV upload | ✅ | — | ✅ | ✅ | pandas |
| Excel upload | ✅ | — | ✅ per sheet | ✅ | openpyxl |
| Custom | — | — | — | — | Implement `BaseConnector` |

All credentials encrypted at rest using Fernet per-org DEK.

---

## Security

- JWT auth (HS256, Redis revocation list)
- RBAC: 18 permissions × 6 system roles
- Audit log: HMAC-chained for tamper detection
- LLM API keys encrypted at rest (Fernet, per-org DEK)
- Connector credentials encrypted at rest (Fernet, per-org DEK)
- LLM provider `extra_config` fields encrypted at rest (SEC-010, wave-2)
- Per-org DEK rotation via `POST /admin/org/rotate-dek` (DI-C1, wave-2)
- Artifact frontmatter scrubbing before storage (SEC-011, wave-2)
- Per-org isolation enforced at every query
- SlowAPI rate limiting on sensitive endpoints
- Sentry + OpenTelemetry support
- No telemetry by default (everything self-hosted)

See [SECURITY.md](SECURITY.md) for the vuln disclosure policy.

---

## Documentation

| File | What |
|------|------|
| [DEPLOY.md](DEPLOY.md) | Full deployment guide — quick-start, GCP one-VM, Caddy TLS, Alembic upgrade notes, ops, troubleshooting |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Shipped features + upcoming roadmap |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Dev setup, branching, PR conventions |
| [SECURITY.md](SECURITY.md) | Vulnerability disclosure |
| [docs/MIGRATION_NOTES.md](docs/MIGRATION_NOTES.md) | Alembic upgrade runbook for existing installs |
| [docs/FRONTEND_DESIGN_BRIEF.md](docs/FRONTEND_DESIGN_BRIEF.md) | Frontend redesign brief for design tools |

---

## License

Apache 2.0 — see [LICENSE](LICENSE).

BMAD-METHOD is vendored under `agents/bmad/BMAD-METHOD/` with its own LICENSE
(also Apache 2.0).

---

## Acknowledgements

- [BMAD-METHOD](https://github.com/datainteg/BMAD-METHOD) — the agent framework + 6 personas + task skills.
- [Temporal](https://temporal.io) — durable workflow engine.
- [LangGraph](https://github.com/langchain-ai/langgraph) — agent state machine.
- [PydanticAI](https://ai.pydantic.dev) — typed LLM calls.

---

## Status

v0.3.0 — Core pipeline (13-node BMAD + Temporal + LLM routing + artifact
handoff), SDK/CLI v0.2.0+, pagination envelope, DEK rotation, A11Y AA, and
Caddy TLS are functional. Frontend is being redesigned. Some connectors are
minimal-implementation. Email-based invitations require SMTP configuration.

See [docs/archive/](docs/archive/) for historical planning + design notes.
