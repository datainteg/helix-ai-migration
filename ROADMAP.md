# Roadmap

> **Last updated:** 2026-05-23
> **Single source of truth for what's next:** [FUTURE_IMPROVEMENTS.md](FUTURE_IMPROVEMENTS.md)
> **Capability matrix:** see [README.md → Honest Capability Matrix](README.md#honest-capability-matrix)

## Project Identity

| Item | Value |
|---|---|
| Product | Helix Migration |
| Repository | helix-ai-migration |
| Website | helix.datainteg.io |
| Tagline | Open-source AI-powered migration and validation platform |
| Frontend image | `datainteg/helix-ai-migration-frontend` |
| Backend image | `datainteg/helix-ai-migration-backend` |
| Worker image | `datainteg/helix-ai-migration-worker` |

---

## Status Snapshot (as of 2026-05-23)

| Phase | Stated status (older docs) | Actual status (line-by-line code read) |
|---|---|---|
| Phase 1 — Core Platform | ✅ Complete | ✅ Foundation present. Auth, RBAC, org isolation, project CRUD, LLM provider CRUD, artifact upload all work. Several integration gaps remain (see C-9, H-3, H-16 in FUTURE_IMPROVEMENTS.md). |
| Phase 2 — Developer Workspace | ✅ Complete | 🟡 Partial. Upload + analyze + review APIs work; conversion endpoint writes invalid data (C-4); UI on `/projects/{id}/developer-workspace` is a static mockup; code review page expects fields backend doesn't return (H-14). |
| Phase 3 — Validation & Recon | ✅ Complete | 🔴 Stub. API returns hardcoded numbers; frontend renders fixtures. Real `recon_service.run_row_count_recon` exists but is not wired (C-2). |
| Phase 4 — Governance & Observability | ✅ Complete | 🟡 Partial. Audit table + endpoint exist but only first-admin and LLM provider CRUD actually audit. System health reports `"unknown"` for Redis / Temporal / Worker (H-19). |
| Phase 5 — Templates & Plugins | 🔜 Planned | 🔜 Not started. Custom connector registry exists (`connectors/custom/registry.py`); no templates / plugin lifecycle yet. |
| Phase 6 — Enterprise Hardening | 🔜 Planned | 🔜 Not started. No SSO, no Helm chart, no per-org KEK, no rate limiting. |
| Phase 7 — Advanced AI | 🔜 Planned | 🔜 Not started. BMAD nodes do not yet call any LLM (C-7); 4 of 13 agents wired into graph. |

---

## ✅ Implemented Today

- Repository structure + Docker Compose (7 services in dev compose)
- Frontend Next.js shell (17 page routes, 23 TSX/TS files)
- Backend FastAPI (13 routers, 10 services, 9 models, 7 Alembic migrations)
- Authentication (JWT HS256, bcrypt, RBAC with 7 roles / 17 permissions, org isolation)
- LLM provider CRUD (7 provider types modeled; OpenAI-compatible `test_connection` only)
- Fernet encryption + masking of API keys
- BMAD + LangGraph 4-node graph (BA, Architect, Validation Planner, Approval Gate) — **outputs hardcoded, not LLM-generated**
- PydanticAI-compatible structured output runtime
- Temporal workflow / activity / worker code (worker Docker image broken — see C-1)
- Workflow persistence (`workflow_runs`, `workflow_steps`)
- Safe artifact upload (.py / .sql, 25 MB cap, UUID names, path-traversal guarded)
- Functional connectors: **PostgreSQL, CSV, Excel**
- Skeleton connectors: MySQL, SQL Server, Snowflake, S3
- `useApi()` hook (defined, not yet used by pages)
- Tests: 60 total, 58 pass, 2 skipped (Temporal integration)

## 🟡 Partial / Stubbed

- BMAD agent execution (hardcoded outputs)
- Code review UI (backend / frontend contract mismatch)
- Validation engine (API stub)
- Reconciliation engine (API stub, real service unwired)
- Audit logging (only 2 endpoints audit)
- System health probes (3 of 5 components hardcoded "unknown")
- Code conversion (writes fake `content_hash`, unsafe storage path)
- Workflow approval persistence (returns success without writing)

## 🔴 Missing

- Rate limiting on any endpoint
- JWT revocation / token blacklist
- Password strength validation
- SSL/TLS enforcement on connectors
- URL-encoded credentials in connection strings
- SSRF protection on LLM `base_url` and connector test
- Per-org DEK / envelope encryption
- Frontend tests (no Playwright, no Vitest)
- CI/CD workflows
- Structured logging, OTel tracing, Prometheus metrics, Sentry
- Helm chart
- SSO / OAuth

---

## Forward Plan (Quarterly)

The single prioritized engineering plan lives in **[FUTURE_IMPROVEMENTS.md](FUTURE_IMPROVEMENTS.md)**. Below is the high-level quarterly view; it tracks the same items.

### Q1 — Foundation & Security Hardening
- All P0 criticals (C-1 through C-10) closed.
- Rate limiting, password strength, token revocation, audit-everywhere, CORS hardening (H-1 through H-7).
- CI/CD scaffold.
- Honest validation / reconciliation in UI (either real, or labeled "demo").

### Q2 — Performance & Reliability
- Implement MySQL, SQL Server, Snowflake, S3 connectors.
- Real validation engine (schema-compare + row-count + null-count).
- Per-node Temporal activities + Signal-based approval.
- Structured logging, OpenTelemetry, Prometheus, Sentry.
- Per-org DEK envelope encryption.
- Test coverage to 75%.

### Q3 — Features & Polish
- Wire all 13 BMAD agents into LangGraph (fan-out where independent).
- SSO/OAuth.
- Kubernetes Helm chart.
- Plugin system foundations.
- Audit log tamper-evidence.
- WebSocket workflow progress.
- Migration templates and validation libraries.

### Q4 — Advanced AI & Ecosystem
- Best-of-N model comparison.
- Migration simulator.
- AI mismatch explanations.
- Local LLM full support (Ollama, vLLM, LM Studio).
- Sensitive-data safe mode.
- Knowledge memory + lineage visualization.

---

## Reference Docs

- [README.md](README.md) — entry point and capability matrix
- [ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md) — full system review
- [FUTURE_IMPROVEMENTS.md](FUTURE_IMPROVEMENTS.md) — prioritized engineering plan
- [CODE_REVIEW.md](CODE_REVIEW.md) — prompt-driven audit (historical)
- [IMPROVEMENTS.md](IMPROVEMENTS.md) — line-by-line review (historical)
- [SECURITY.md](SECURITY.md) — security model + planned hardening
- [ARCHITECTURE.md](ARCHITECTURE.md), [API_DESIGN.md](API_DESIGN.md), [DATABASE_DESIGN.md](DATABASE_DESIGN.md), [AGENT_WORKFLOW.md](AGENT_WORKFLOW.md), [DOCKER_GUIDE.md](DOCKER_GUIDE.md) — design references
