# Helix Migration — Future Improvements

> **Last updated:** 2026-05-23
> **Source:** Line-by-line code review of all ~110 source files (backend, agents, worker, connectors, frontend, Docker, tests). Cross-referenced with [ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md), [CODE_REVIEW.md](CODE_REVIEW.md), and [IMPROVEMENTS.md](IMPROVEMENTS.md).
> **Owner:** Engineering team
> **Review cadence:** Quarterly, or after every major release.

This document is the **single prioritized engineering plan** for Helix Migration. It replaces nothing; it is the actionable layer above the existing architectural and line-by-line review documents.

Each item has: a unique ID, a one-line problem statement, a recommended fix, a time estimate, the file(s) involved, and a priority tier.

---

## Priority Tiers

| Tier | Meaning | Target window |
|---|---|---|
| **P0 — Critical** | Production blocker, capability misrepresentation, or security exposure | Within 1 week |
| **P1 — High** | Required before "1.0" release; security hardening; capability gaps the UI claims | Within 1 sprint (2-3 weeks) |
| **P2 — Medium** | Quality, performance, code health | Next 1-2 months |
| **P3 — Low** | Nice to have, polish, future-proofing | Backlog |

---

## P0 — Critical (fix before any production use)

### C-1. Fix worker Dockerfile
**Problem:** `worker/Dockerfile` has no `pip install -r requirements.txt`, so the worker container fails on `from temporalio.client import Client`.
**Fix:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```
**Files:** `worker/Dockerfile`
**Estimate:** 5 minutes
**Verification:** `docker compose -f docker-compose.dev.yml build helix-ai-migration-worker && docker compose -f docker-compose.dev.yml up helix-ai-migration-worker` — logs show `"Connected to Temporal server"`.

### C-2. Remove or label fake validation/reconciliation outputs
**Problem:** `POST /projects/{id}/validation-runs` writes `status="completed"` without running any check. `POST /projects/{id}/recon-runs` returns hardcoded `"Source: 150000 rows, Target: 149998 rows. Difference: 2"`. The validation and reconciliation frontend pages render hardcoded fixture data, not API results. A user can plausibly believe these numbers reflect real comparisons.
**Fix:**
1. Wire `recon_service.run_row_count_recon` (already exists) into `POST /projects/{id}/recon-runs`. Require a `source` and `target` connection ID payload.
2. Stop the frontend pages from rendering hardcoded data — fetch from the API and show an `EmptyState` if no run exists.
3. Until full validation is implemented, return `{"mode": "demo", ...}` from the validation endpoint and add a banner on the UI.
**Files:** `backend/app/api/validation.py`, `frontend/src/app/validation/page.tsx`, `frontend/src/app/reconciliation/page.tsx`
**Estimate:** 1-2 days

### C-3. Close cross-org LLM provider leak in code analyzer/reviewer
**Problem:** `agents/code_analyzer_agent/analyzer.py:77` calls `_try_llm_call(source_code, filename)` with no `org_id`. The default `org_id=None` causes the internal query to skip the organization filter and pick the first active provider globally.
**Fix:** Make `org_id` a required parameter of `analyze_code()` and `review_code()`. Pass it from `backend/app/api/code_reviews.py` (which already has `org_id`). Better: route every agent LLM call through `agents.runtime.llm_router.route_llm_call()` with a future `org_id` argument.
**Files:** `agents/code_analyzer_agent/analyzer.py`, `agents/code_review_agent/reviewer.py`, `backend/app/api/code_reviews.py`
**Estimate:** 1-2 hours

### C-4. Fix `code_conversion.py` invariants
**Problem:** `start_conversion()` writes `content_hash="generated_draft_hash"` (a literal string, not a hash) and `storage_path=f"/drafts/{...}"` (outside `ARTIFACT_STORAGE_PATH` and never validated through `_assert_inside_storage_root`). No file is written, so any downstream reader hits FileNotFoundError.
**Fix:** Either gate the endpoint behind a feature flag until real conversion is implemented, or generate a templated draft file, hash it with `hashlib.sha256`, and route the path through `build_safe_artifact_path()` + `save_artifact_file()`.
**Files:** `backend/app/api/code_conversion.py`
**Estimate:** 2-3 hours

### C-5. Add rate limiting to auth, connector-test, and LLM-test endpoints
**Problem:** No `slowapi` or equivalent. `POST /auth/login` accepts unlimited bcrypt-bounded attempts. `POST /connectors/test` accepts arbitrary host + credentials and proxies outbound traffic from the backend — **SSRF + open outbound proxy**. `POST /llm-providers/{id}/test` accepts a configured `base_url` and connects to it.
**Fix:** Install `slowapi`, register a global `Limiter` with `key_func=get_remote_address` and Redis backend. Apply:
- `5/minute` on `/auth/login`
- `2/minute` on `/auth/first-admin`
- `10/minute` on `/connectors/test`
- `10/minute` on `/llm-providers/{id}/test`
Add an allowlist (per org or global) of permitted LLM base URLs to limit SSRF.
**Files:** `backend/app/main.py`, `backend/app/api/auth.py`, `backend/app/api/connectors.py`, `backend/app/api/llm_providers.py`, `backend/requirements.txt`
**Estimate:** 4-6 hours

### C-6. URL-encode database credentials in PostgreSQL connector
**Problem:** [connectors/postgres/connector.py:45](connectors/postgres/connector.py#L45) builds `postgresql://{username}:{password}@{host}:{port}/{database}` via plain f-string. Any password containing `@`, `:`, `/`, `?`, `#`, or `%` corrupts the URL — at best a confusing error, at worst credential disclosure in logs that include the malformed URL.
**Fix:**
```python
from urllib.parse import quote_plus
return f"postgresql://{quote_plus(username)}:{quote_plus(password)}@{host}:{port}/{quote_plus(database)}"
```
Audit MySQL, SQL Server, Snowflake connectors as they are implemented.
**Files:** `connectors/postgres/connector.py`
**Estimate:** 30 minutes

### C-7. Wire BMAD nodes through `route_llm_call` instead of hardcoded outputs
**Problem:** [agents/bmad/nodes.py:54-144](agents/bmad/nodes.py#L54-L144) constructs `BusinessAnalystOutput`, `ArchitectOutput`, `ValidationPlanOutput` with fixed strings. The user's `requirement_text` is in state but unused by these nodes. The frontend presents the canned text as AI-generated.
**Fix:** Inside each node, build a prompt with `build_mock_agent_prompt(agent_key, state["requirement_text"])`, call `route_llm_call(...)` resolved against the org's configured provider (defaulting to mock mode if no provider), and parse the response with `parse_router_result(result, OutputSchema)`. Use `build_mock_agent_response()` from `agents/runtime/structured_output.py` for mock mode — it already exists. Keep tests using mock mode.
**Files:** `agents/bmad/nodes.py`, `agents/runtime/llm_router.py` (extend to accept `org_id` and resolve the provider)
**Estimate:** 1-2 days

### C-8. Remove `sys.path` mutation from agents
**Problem:** [agents/code_analyzer_agent/analyzer.py:20-22](agents/code_analyzer_agent/analyzer.py#L20-L22) and [agents/code_review_agent/reviewer.py:18-20](agents/code_review_agent/reviewer.py#L18-L20) mutate global `sys.path` at import time so `backend.app.*` is importable. The worker also does this. This is a packaging anti-pattern that hides circular dependencies and breaks if either layer is installed via pip.
**Fix:** Make backend and agents proper installable packages (`pyproject.toml` with `[project] name = "helix-backend"` and `name = "helix-agents"`). Update the worker Dockerfile to `pip install -e ../backend && pip install -e ../agents`. Remove all `sys.path.insert`.
**Files:** `agents/code_analyzer_agent/analyzer.py`, `agents/code_review_agent/reviewer.py`, `worker/main.py`, plus new `pyproject.toml` files.
**Estimate:** 1 day

### C-9. Stop persisting fake `WorkflowRun.status="completed"` for approval calls
**Problem:** [backend/app/api/agent_workflows.py:84-95](backend/app/api/agent_workflows.py#L84-L95) returns `{"workflow_id": ..., "decision": ..., "status": "recorded"}` but does not update `WorkflowRun.status`, does not write an audit row, does not validate the decision against the workflow's actual state.
**Fix:** Implement persistence:
```python
@router.post("/agent-workflows/{workflow_id}/approve")
def approve_step(workflow_id: str, data: ApprovalRequest, db: Session = Depends(get_db), ...):
    run = db.query(WorkflowRun).filter_by(workflow_id=workflow_id).first()
    if not run: raise HTTPException(404)
    if data.decision not in ("approved", "rejected"): raise HTTPException(400)
    run.status = data.decision
    db.commit()
    write_audit(db, run.organization_id, user_id, f"workflow_{data.decision}", "workflow_run", workflow_id, meta={"notes": data.notes})
    return {"workflow_id": workflow_id, "decision": data.decision, "status": run.status}
```
**Files:** `backend/app/api/agent_workflows.py`
**Estimate:** 2 hours

### C-10. Remove dead code in `list_workflows`
**Problem:** [backend/app/api/agent_workflows.py:105-109](backend/app/api/agent_workflows.py#L105-L109) has `return []` followed by unreachable `return {"project_id": project_id, "workflows": []}`. The endpoint exists in the router but is documented in `CODE_REVIEW.md` as "implemented".
**Fix:** Implement properly using `workflow_service.list_workflow_runs(db, org_id, project_id)` and return a list of run summaries.
**Files:** `backend/app/api/agent_workflows.py`
**Estimate:** 30 minutes

---

## P1 — High (close before "1.0" / before charging customers)

### H-1. Token revocation and JWT `jti`
- Add a `jti` claim on token creation, store in Redis with TTL = token lifetime on `/auth/logout`, check in `get_current_user_id`.
- Optional: switch to `httpOnly; Secure; SameSite=Strict` cookies if the XSS surface justifies the operational complexity.
**Files:** `backend/app/auth/jwt.py`, `backend/app/api/auth.py`, new logout route
**Estimate:** 1 day

### H-2. Password strength validation
- Add a `password_strength` validator: min 12 chars, requires upper/lower/digit/symbol, denies a common-passwords list.
- Validate on `FirstAdminSetup` and future user-create routes.
**Files:** `backend/app/schemas/identity.py`, `backend/app/services/auth_service.py`
**Estimate:** 4 hours

### H-3. Audit every state-changing endpoint
**Problem:** Today only `auth/first-admin` and LLM provider CRUD write audit rows.
**Fix:** Add `write_audit(...)` calls on project create, requirement create, source/target connection create, artifact upload, artifact analyze/review, artifact approve/reject, workflow start, workflow approve, validation/recon run, system setting changes.
**Files:** `backend/app/api/*`
**Estimate:** 1-2 days

### H-4. SSL/TLS enforcement on connector connections
- PostgreSQL: default `sslmode=require` in connection URL.
- MySQL / Snowflake / SQL Server (when implemented): same.
**Files:** `connectors/postgres/connector.py` (and future connectors)
**Estimate:** 2 hours

### H-5. Connector test endpoint requires project scope + audit
**Problem:** [backend/app/api/connectors.py](backend/app/api/connectors.py) accepts a raw `config: dict` with no project scope, no rate limit, no audit. Combined with C-5, it's the highest-risk endpoint in the system.
**Fix:** Require a `project_id` parameter, enforce `ensure_project_access`, audit every attempt (without password), apply rate limit.
**Files:** `backend/app/api/connectors.py`
**Estimate:** 4 hours

### H-6. Switch from `String` to proper types in models
**Problem:** Many models use `String(50)` for `started_at`, `finished_at`, `approved_at`, `rotated_at`, `completed_at`, `version_number`, `row_count`, `mismatch_count`, `step_order`. These should be `DateTime`, `Integer`, `Integer`, etc. Lexicographic ordering on these columns produces wrong results today (`"10" < "2"`).
**Fix:** Alembic migration to convert column types, update model definitions, update any code that does `str(int(version.version_number) + 1)`.
**Files:** Multiple models + new Alembic migration
**Estimate:** 1 day

### H-7. CORS hardening
- Restrict `allow_methods` to `["GET", "POST", "PUT", "PATCH", "DELETE"]`.
- Restrict `allow_headers` to actually-used headers (Authorization, Content-Type).
- Validate `CORS_ORIGINS` rejects `*` when `APP_ENV=production`.
**Files:** `backend/app/main.py`, `backend/app/core/config.py`
**Estimate:** 1 hour

### H-8. Eager-load role permissions to kill N+1
**Problem:** `user_has_permission` triggers ≥3 queries per protected request. Login + dashboard view fires ~15 queries.
**Fix:** `selectinload(Role.permissions)` in `_role_for_membership`. Or cache the resolved `set[permission_code]` per user in Redis with 60-second TTL.
**Files:** `backend/app/auth/dependencies.py`
**Estimate:** 2 hours

### H-9. Strong `ENCRYPTION_KEY` validation
**Problem:** `_get_fernet()` SHA-256-derives a Fernet key from any string. `password123` becomes a "valid" key.
**Fix:** Require a base64-encoded 32-byte key (output of `Fernet.generate_key()`). Reject anything else at startup.
**Files:** `backend/app/services/secret_service.py`, `backend/app/core/config.py`
**Estimate:** 3 hours

### H-10. Backend / worker Dockerfile hardening
- Multi-stage build (`builder` + `runner`).
- Non-root user (`USER 1000`).
- `HEALTHCHECK CMD curl -fsS http://localhost:8000/api/v1/health || exit 1`.
- `.dockerignore` to exclude tests, `__pycache__`, `.venv`, `.pytest_cache`.
**Files:** `backend/Dockerfile`, `worker/Dockerfile`, new `.dockerignore`
**Estimate:** 4 hours

### H-11. Remove hardcoded DB password from `docker-compose.yml`
**Problem:** Both dev and prod compose files ship `POSTGRES_PASSWORD: helix_password`. Anyone pulling the published images and running prod compose gets a system with a known password.
**Fix:** Production compose must require `POSTGRES_PASSWORD` from env with no default. Add a `secrets:` section for `JWT_SECRET_KEY` and `ENCRYPTION_KEY`. Document in `DOCKER_GUIDE.md`.
**Files:** `docker-compose.yml`, `DOCKER_GUIDE.md`
**Estimate:** 2 hours

### H-12. Implement MySQL connector (full)
- Use the PostgreSQL connector as a template.
- `mysql+pymysql://` driver, `SHOW DATABASES` for schemas, `INFORMATION_SCHEMA.TABLES`/`COLUMNS` for discovery.
- Force `ssl_disabled=False`.
- Add tests mirroring `test_connectors.TestPostgresConnector`.
**Files:** `connectors/mysql/connector.py`, `backend/requirements.txt` (`pymysql`), `backend/tests/test_connectors.py`
**Estimate:** 1 day

### H-13. Frontend `useApi()` adoption + UI primitives
- Migrate all 17 pages to use `useApi()` instead of inline fetch.
- Extract `<Card>`, `<EmptyState>`, `<LoadingState>`, `<ErrorBanner>`, `<Button>` components.
- Reduces ~30% of frontend page code.
**Files:** All `frontend/src/app/**/*.tsx`, new `frontend/src/components/ui/`
**Estimate:** 2-3 days

### H-14. Frontend code-review page contract alignment
**Problem:** [frontend/src/app/developer-workspace/[id]/page.tsx](frontend/src/app/developer-workspace/[id]/page.tsx) expects fields (`inputs_detected`, `outputs_detected`, `quality_score`, `migration_suggestions`, `validation_requirements`) that the backend `CodeReviewOutput` schema does not return. Page renders empty.
**Fix:** Align on a single schema. Either add the missing fields to `CodeReviewOutput` or rewrite the frontend to use the actual returned shape (`quality_findings`, `anti_patterns`, `security_findings`, `hardcoded_secrets_detected`, …).
**Files:** `frontend/src/app/developer-workspace/[id]/page.tsx`, `agents/schemas/developer_agents.py`
**Estimate:** 4 hours

### H-15. Developer workspace upload page — project selector is empty
**Problem:** [frontend/src/app/developer-workspace/page.tsx:110-115](frontend/src/app/developer-workspace/page.tsx) `<select>` only renders the placeholder option, never the fetched projects (the fetched list is dropped on the floor by the `useEffect`).
**Fix:** Add `projects.map(p => <option value={p.id}>{p.name}</option>)`.
**Files:** `frontend/src/app/developer-workspace/page.tsx`
**Estimate:** 15 minutes

### H-16. `ProjectCreate` schema is missing `migration_type`
**Problem:** [frontend/src/app/projects/new/page.tsx:26](frontend/src/app/projects/new/page.tsx) sends `migration_type: "database"` but [backend/app/schemas/project.py:5-8](backend/app/schemas/project.py#L5-L8) drops it (Pydantic ignores extras by default). Data loss with no error.
**Fix:** Add `migration_type: Optional[str] = None` to `ProjectCreate`, add column to `Project` model, Alembic migration.
**Files:** `backend/app/schemas/project.py`, `backend/app/models/project.py`, `backend/app/services/project_service.py`, new Alembic migration
**Estimate:** 2 hours

### H-17. CI/CD pipeline scaffold
Create `.github/workflows/ci.yml`:
- Backend: `pip install -r requirements.txt && pytest tests/ -v`
- Frontend: `npm ci && npm run build && npm run lint`
- Static analysis: `ruff check`, `mypy`
- Security: `pip-audit`, `npm audit`
- Optional: `docker build` to verify all three Dockerfiles
**Files:** new `.github/workflows/ci.yml`, `pyproject.toml` (ruff/mypy config)
**Estimate:** 1 day

### H-18. Implement real validation engine: schema-compare + row-count
- Schema-compare: pull `list_columns()` from source and target, return `added`, `removed`, `type_diff` lists.
- Row-count: already wired (recon_service); expose as a validation rule type.
- Null-count: parameterized query per column.
- Persist results in `ValidationResult`.
**Files:** `backend/app/services/` new `validation_service.py`, `backend/app/api/validation.py`, `connectors/postgres/connector.py` (parameterized null-count helper)
**Estimate:** 3-5 days

### H-19. Real system health probes
**Problem:** `/system/health` reports `"unknown"` for Redis, Temporal, Worker.
**Fix:**
- Redis: `redis_client.ping()` with 1 s timeout.
- Temporal: `await Client.connect(TEMPORAL_ADDRESS, namespace=..., tls=...)` with 2 s timeout.
- Worker: query Temporal for active workers on the task queue.
**Files:** `backend/app/api/system.py`
**Estimate:** 4 hours

### H-20. Connection engine caching in PostgreSQL connector
**Problem:** Every `test_connection`, `list_schemas`, `list_tables`, `list_columns`, `get_row_count` builds a fresh SQLAlchemy `Engine`. Schema discovery for a 50-table source pays 50× the connection cost.
**Fix:** Lazy-init `self._engine` on first use, expose `close()`.
**Files:** `connectors/postgres/connector.py`
**Estimate:** 2 hours

---

## P2 — Medium (next 1-2 months)

### M-1. TanStack Query + Zustand
- Add `@tanstack/react-query`, wrap `_layout.tsx` with `QueryClientProvider`.
- Convert every `useEffect → fetch` to `useQuery`/`useMutation`.
- Use Zustand for selected project, sidebar collapse, etc.
**Estimate:** 2-3 days

### M-2. OpenAPI-driven TypeScript types in frontend
- Add `openapi-typescript` as a dev dep.
- `npm run gen:types` calls `npx openapi-typescript http://localhost:8000/openapi.json -o src/lib/api-types.ts`.
- Replace ad-hoc interfaces with generated types.
**Estimate:** 1 day

### M-3. Structured logging + correlation IDs
- `python-json-logger` for JSON output.
- Middleware injects/propagates `X-Request-ID`.
- Bind to log context so every line carries the request ID.
**Estimate:** 1 day

### M-4. OpenTelemetry instrumentation
- `opentelemetry-instrumentation-fastapi`, `-sqlalchemy`, `-httpx`.
- Workflow `workflow.info().workflow_id` propagated as trace ID.
**Estimate:** 2 days

### M-5. Prometheus metrics
- `prometheus-fastapi-instrumentator` for HTTP metrics.
- Custom metrics: `agent_run_total`, `workflow_duration_seconds`, `llm_token_usage`.
**Estimate:** 1 day

### M-6. Sentry SDK
- Auto-capture unhandled exceptions.
- Tag with `organization_id`, `workflow_id` where available.
**Estimate:** 4 hours

### M-7. SQL Server connector (full)
- `mssql+pyodbc://` driver, `INFORMATION_SCHEMA` queries.
- Force `Encrypt=yes; TrustServerCertificate=no`.
**Estimate:** 1-2 days

### M-8. Snowflake connector (full)
- `snowflake-sqlalchemy` driver.
- Account, warehouse, role, database, schema in config.
- TLS enforced by Snowflake.
**Estimate:** 1-2 days

### M-9. S3 connector (full)
- `boto3` for listing and `s3fs` for read.
- Bucket + prefix in config; never persist credentials, accept STS role assumption.
**Estimate:** 1-2 days

### M-10. Per-node Temporal activities + Signal-based approval
- One activity per BMAD node (better progress visibility, finer retry).
- Replace the approval gate node with a Temporal Signal (`await workflow.wait_condition(...)`).
**Estimate:** 3-4 days

### M-11. WebSocket / SSE for live workflow progress
- Stream workflow + step state from the backend.
- Frontend subscribes via `EventSource`.
**Estimate:** 2-3 days

### M-12. Per-org DEK + envelope encryption
- Each org has a randomly generated DEK (Data Encryption Key) at create time.
- The KEK (Key Encryption Key) lives in env / Vault and decrypts DEKs.
- Rotating the KEK re-encrypts DEKs, not every secret.
**Estimate:** 3 days

### M-13. Audit log tamper-evidence
- Each log row carries a hash of `previous_log_id || row_bytes`.
- Verification job runs on schedule, alerts on gap.
**Estimate:** 2 days

### M-14. JSONB conversion for `WorkflowStep.parsed_output_json`
- Alembic migration: `Text → JSONB` (Postgres) / keep `Text` on SQLite.
- Stop double-serializing in `save_workflow_step`.
**Estimate:** 4 hours

### M-15. Composite indexes
```sql
CREATE INDEX ix_workflow_runs_org_created ON workflow_runs(organization_id, created_at DESC);
CREATE INDEX ix_audit_logs_org_created ON audit_logs(organization_id, created_at DESC);
CREATE INDEX ix_artifacts_org_project ON code_artifacts(organization_id, project_id);
```
**Estimate:** 2 hours

### M-16. Async SQLAlchemy on read-heavy endpoints
- `asyncpg` + `AsyncSession` for `/projects`, `/audit-logs`, `/agent-workflows` list endpoints.
- Sync everywhere else stays unchanged.
**Estimate:** 2-3 days

### M-17. Refactor `code_analyzer_agent` and `code_review_agent` to share LLM client
- Extract `_try_llm_call` to `agents/runtime/llm_client.py` once.
- Eliminate ~80 lines of duplicated code.
**Estimate:** 4 hours

### M-18. Implement password reset flow
- `/auth/forgot-password` issues a single-use token (Redis, 15 min TTL).
- Email via SMTP (config already in `.env.example`).
- `/auth/reset-password` consumes the token.
**Estimate:** 2 days

### M-19. Test coverage to 75%
- Add `pytest-cov` with `--cov-fail-under=75`.
- Fill gaps in workflow service, recon service, identifier adversarial inputs.
**Estimate:** 2-3 days

### M-20. Frontend Playwright E2E
- 3 happy-path scenarios: login → create-project → run-workflow; admin LLM CRUD; artifact upload + review.
- Run in CI against `docker compose up`.
**Estimate:** 2 days

### M-21. Replace `RiskItem.severity: str` with `Literal`
- `Literal["low", "medium", "high", "critical"]` in `agents/bmad/schemas.py` and `agents/schemas/developer_agents.py`.
**Estimate:** 30 minutes

### M-22. Cache compiled BMAD graph correctly across tests
- Add a `force_rebuild` parameter to `build_bmad_graph()` so tests can request a fresh graph.
**Estimate:** 1 hour

### M-23. Implement remaining LLM provider adapters
- `AnthropicAdapter` — `POST /v1/messages` with `anthropic-version` header.
- `GeminiAdapter` — `POST /v1beta/models/{model}:generateContent`.
- `LocalModelAdapter` — Ollama (`POST /api/generate`) and LM Studio fallback.
**Estimate:** 2 days

### M-24. Request body size limit middleware
- Enforce `Content-Length <= MAX_UPLOAD_BYTES + 1MB` before reading the body.
**Estimate:** 2 hours

### M-25. Pre-commit hooks
- `ruff`, `black`, `isort` for Python.
- `prettier`, `eslint` for TS.
- `detect-secrets` to catch accidental credential commits.
**Estimate:** 2 hours

---

## P3 — Low (backlog, polish, future-proofing)

- **L-1.** Replace bare HTTP status codes with `http.HTTPStatus`.
- **L-2.** Move `from fastapi import HTTPException` inline imports to module top.
- **L-3.** Add `pyproject.toml` with `[project]` and `[tool.*]` config.
- **L-4.** Migrate from `String(36)` UUID columns to PG `UUID` type when Postgres-only.
- **L-5.** Replace `Record<string, unknown>` with proper interfaces in frontend.
- **L-6.** Cache `get_official_agent_metadata` at module load.
- **L-7.** Store `key_prefix` (last 4 chars) at create/rotate time so `_to_response` can mask without decrypting.
- **L-8.** Replace `String(20)` `version_number` with `Integer`; same for `step_order`, `row_count`, `mismatch_count`.
- **L-9.** Standardize success response envelope (`{data: ..., meta: ...}` vs. resource-direct).
- **L-10.** Partition `audit_logs` and `workflow_steps` by month when row count crosses 10M.
- **L-11.** ADRs (`docs/adr/`) for Temporal, BMAD, LangGraph, Postgres-metadata-only.
- **L-12.** "How to add a new BMAD agent" guide.
- **L-13.** "How to add a new connector" guide.
- **L-14.** Remove vendored `agents/bmad/BMAD-METHOD/` test/fixture subdirectories that aren't loaded at runtime.
- **L-15.** Use `http.HTTPStatus` enum consistently in Python.
- **L-16.** Consider migrating from `python-jose` (less maintained) to `PyJWT`.
- **L-17.** Add Renovate or Dependabot for upstream dependency updates.
- **L-18.** Lock files (`pip-tools` or `uv` for backend; `package-lock.json` committed for frontend).
- **L-19.** Docker image digest pinning for base images.
- **L-20.** Streaming reads for CSV / Excel connectors (current implementation loads entire file).

---

## Roadmap (quarterly view)

### Q1 — Foundation & Security Hardening
Close all P0 (C-1 through C-10). Land H-1 through H-7. Ship CI/CD scaffold (H-17). Replace fake validation/recon UI with real or honest-demo. Result: platform is **honest about what it does** and **safe enough to run for internal pilots**.

### Q2 — Performance & Reliability
Wire all four remaining connectors (MySQL, SQL Server, Snowflake, S3). Real validation engine (H-18). Per-node Temporal activities + Signal-based approval (M-10). Structured logging + OTel + Prometheus + Sentry (M-3, M-4, M-5, M-6). Per-org DEK envelope encryption (M-12). Test coverage to 75%. Result: platform handles real connectors at real volume with real observability.

### Q3 — Features & Polish
Wire all 13 BMAD agents into LangGraph (fan-out for parallel agents). SSO/OAuth. Helm chart. Plugin system foundations. Audit log tamper-evidence (M-13). WebSocket workflow progress (M-11). Migration templates and validation libraries. Result: enterprise-deployable, contributor-friendly OSS.

### Q4 — Advanced AI & Ecosystem
Best-of-N model comparison. Migration simulator. AI mismatch explanations. Local LLM full support (Ollama, vLLM, LM Studio). Sensitive-data safe mode. Knowledge memory / lineage. Result: differentiated AI capability, defensible product moat.

---

## Tracking & Reviews

- This document is authoritative. When something here is landed, mark it ✅ at the start of the line (do not delete — keeps history).
- Cross-link to GitHub issues by ID. Each P0 item should have a tracking issue within a week of merging this plan.
- Re-review quarterly. Each review should:
  1. Move completed items to a "Completed" section at the end.
  2. Re-tier any items whose priority changed.
  3. Pull in new findings from the next full architectural review.

---

## Source Material

- [ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md) — 18-section deep review, criticals + corrections.
- [CODE_REVIEW.md](CODE_REVIEW.md) — File-to-prompt audit (prompt-driven).
- [IMPROVEMENTS.md](IMPROVEMENTS.md) — Line-by-line review findings.
- Source code (all ~110 files read line-by-line on 2026-05-23).

---

**Maintainer note:** This file replaces older "quick wins / medium-term / long-term" lists scattered across `IMPROVEMENTS.md`, `ROADMAP.md`, and `CODE_REVIEW.md`. Those documents remain as historical artifacts and reference material. Use this file as the source of truth for "what we're doing next".
