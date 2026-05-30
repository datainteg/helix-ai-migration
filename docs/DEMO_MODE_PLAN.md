# Helix — Backend-Driven Demo Mode + Frontend De-Mock: Implementation & Migration Plan

> Lead-engineer design document. No code — designs, contracts, file-level checklists, ordered milestones.
> Hard constraints honored throughout: **PostgreSQL only** (no Mongo); demo = a **real seeded org behind a real login**, never a frontend bypass; **real-user isolation guaranteed** by existing multi-tenancy; **frontend consumes APIs only**.

---

## 1. Executive Summary + Current-State Recap

### 1.1 Goal
Ship a "Login with Demo User" button that authenticates a **pre-seeded real demo account** in a **dedicated demo organization**, so that every authenticated page renders **real Postgres data through the same APIs real customers hit**. Simultaneously, remove **all** hardcoded/mock data from the frontend so that:
- The **demo org** looks production-rich (because Postgres is seeded for it).
- A **fresh real org** looks correctly empty (skeletons / empty states), never showing fabricated rows.
- A **real org with data** sees only its own data.

### 1.2 Why this is safe by construction
Isolation is **structural, not special-cased**. Confirmed in `backend/app/auth/dependencies.py`:
- `get_current_organization_id` → `_active_membership` returns the first `OrganizationMember` with `status=="active"` (line 19–37). It **ignores** any `X-Active-Org-Id` header.
- Every domain router/service filters by `organization_id`; cross-org reads return 404/empty.
Therefore a demo user that is a **normal account** (not super-admin) with **exactly one** active membership in the demo org is permanently scoped to demo data, and real users can never query demo rows. **No per-router changes** are needed for real-user safety.

### 1.3 Real vs Mock split (current state)
**Already REAL (keep, just ensure seeded so demo is non-empty):**
- `/dashboard` top metric strip + LLM spend row → `GET /api/v1/dashboard/stats`, `GET /api/v1/usage/llm?days=30` (`backend/app/api/dashboard.py`, `usage.py`). Shapes confirmed in `frontend/src/lib/dashboard/api.ts` (StatsWire) + `lib/usage/api.ts` (UsageSummary).
- `/agents` org run **list** → `GET /api/v1/agent-workflows` (`listOrgWorkflowRuns`).
- `/connectors` grid → `GET /api/v1/connectors/registry`.
- `/admin/system-health` → `GET /api/v1/system/health`. `/knowledge`, `/marketplace`, sprint pages — fully API-wired.

**MOCK pages (entire data surfaces fabricated):** `/dashboard` mid/lower sections, `/agents` pipeline+tokens, `/reconciliation`, `/admin` home metrics, `/approval`, `/developer-workspace` (root IDE), and the orphan `features/developer-workspace/VersionHistoryDrawer.tsx`.

**MIXED pages (real header, fake body):** `/validation`, `projects/[id]/agents` (DEMO_FLOW fallback), `projects/[id]/developer-workspace` (fake fallback file list + static diff panes).

### 1.4 Two confirmed bugs (encode as failing→passing tests)
1. **`/admin/users` wrong path** — `frontend/src/app/admin/users/page.tsx:29` fetches `/api/v1/admin/users` (live **404**). Correct path is `/api/v1/superadmin/users` (live **401** = exists; super-admin-gated). **VERIFIED in code.**
2. **`/connectors` faked Test + no-op Save** — `frontend/src/app/connectors/page.tsx:436-441` `runTest()` is `setTimeout(()=>setTestState(Math.random()>0.15?"ok":"fail"),1400)` with hardcoded check strings at lines 451-503; Save calls only `onClose()`. The REAL `POST /api/v1/connectors/test` exists (live 401). **VERIFIED in code (line 439).**

### 1.5 Infra reality that shapes the design
- Demo workflow detail + SSE **read purely from DB** (`workflow_service.get_workflow_status`; SSE polls DB once/sec and emits `done` for seeded `completed` runs). **No Temporal worker needed** for demo replay. Temporal is required only for live start/signal/replay.
- **APP_ENV is load-bearing** for Temporal hard-enforcement, cookie `Secure`, and SSRF scheme allowlist — **must NOT be reused** as the demo switch.
- Auth is **cookie-only** (`helix_token`, HttpOnly, SameSite=Strict). Demo deploy must stay **same-origin** (Next `/api` proxy) so the cookie is sent.

---

## 2. Architecture Decision: How Demo Mode Works

### 2.1 Decision summary
- **Demo identity:** one dedicated `Organization` (stable `slug="helix-demo"`, new `is_demo=True` flag) + one `User` (`demo@helix.local`, `is_super_admin=False`, `status="active"`) with **exactly one** active `OrganizationMember`.
- **Demo data:** real Postgres rows scoped to the demo org_id, written by an **idempotent seeder** (`app/services/demo_seed.py`), modeled on `app/services/sprint_seed.py`.
- **Demo login:** new **public** `POST /api/v1/auth/demo-login`, gated by `ALLOW_DEMO_LOGIN` env flag, that mints the **same** `helix_token` cookie via the existing `_set_auth_cookie` + `create_access_token`. No password crosses the wire; no client-side bypass.
- **Demo flag:** additive backend setting `ALLOW_DEMO_LOGIN: bool = False` (config.py) + frontend build arg `NEXT_PUBLIC_DEMO_ENABLED`. **APP_ENV untouched.**

### 2.2 Read-only vs ephemeral — DECISION
**v1 = READ-ONLY shared demo org (Option A).** The demo user gets a role with **read-only** permissions (`project:read`, `admin:audit:read` — i.e. the existing `viewer` role from `SYSTEM_ROLES` in `auth_service.py`), so existing `require_permission` gates (`dependencies.py:89-98`) naturally `403` every mutation (`project:write`, `agent:execute`, `artifact:upload`, `validation:execute`, `reconciliation:execute`). This is the least-infra, concurrency-safe choice and prevents concurrent demo sessions corrupting shared rows.

**Follow-up = per-session ephemeral (Option B), explicitly out of v1 scope.** Documented as future work: `/auth/demo-login` would clone a template demo org per session + a TTL reaper keyed on `organizations.is_demo` + `created_at`. Not built in v1 to avoid a clone routine + reaper.

**Consequence for the UI:** in demo mode, all write/start/approve/replay actions must be **disabled with a tooltip** ("Read-only demo"), since the backend will 403 them and Temporal-dependent endpoints (start/signal/replay) would otherwise hang with no worker. See §8.4.

### 2.3 Flow diagram

```
                            ┌────────────────────────────────────────┐
                            │  PUBLIC DEMO DEPLOY (same-origin)        │
                            │  NEXT_PUBLIC_DEMO_ENABLED=true           │
                            │  ALLOW_DEMO_LOGIN=true (backend)         │
                            └────────────────────────────────────────┘
  Browser (/login)
     │  click "Login with Demo User"   (button renders iff NEXT_PUBLIC_DEMO_ENABLED)
     ▼
  POST /api/v1/auth/demo-login   ── same-origin via Next /api proxy ──►  Backend
     │                                                                     │
     │                                            ┌────────────────────────┴───────────┐
     │                                            │ if not ALLOW_DEMO_LOGIN → 403        │
     │                                            │ ensure demo org+user seeded          │
     │                                            │   (demo_seed.seed_demo_org, idemp.)   │
     │                                            │ token=create_access_token(demo_uid)   │
     │                                            │ _set_auth_cookie(helix_token,         │
     │                                            │   HttpOnly, SameSite=strict)          │
     │                                            │ write_audit("demo_login")             │
     │                                            └────────────────────────┬─────────────┘
     ◄──── 200 + Set-Cookie: helix_token ─────────────────────────────────┘
     │
     │  auth-context.refreshUser() → GET /auth/me (200) → router.push('/dashboard')
     ▼
  Every page → GET /api/v1/<module>  (cookie auto-sent, same-origin)
     │
     ▼
  get_current_organization_id → _active_membership(demo_user) → DEMO_ORG_ID
     │
     ▼
  Router/service filter WHERE organization_id = DEMO_ORG_ID
     │
     ▼
  Real seeded Postgres rows  ──►  rendered identically to production

  ── REAL USER (org A) ──► same endpoints ──► _active_membership → ORG_A ──► only org A rows
                                                       (demo rows physically unreachable)
```

---

## 3. Authentication Flow

### 3.1 Current flow (verified)
`POST /api/v1/auth/login` (`auth.py:116`, `@limiter.limit("10/minute")`) → `auth_service.login()` (`auth_service.py:105`): looks up user by email, `verify_password` (bcrypt), rejects `status != "active"`, sets `last_login_at`, returns `create_access_token(str(user.id))`. `_set_auth_cookie` (`auth.py:48-73`) sets `helix_token` HttpOnly, `secure=(APP_ENV=="production" or https)`, `samesite="strict"`, `max_age=JWT_ACCESS_TOKEN_EXPIRE_MINUTES*60`, `path="/"`. JWT carries `sub`, `exp/iat/nbf`, `iss=aud=APP_NAME`, `jti`, `scope="default"` (jwt.py). Every request: `get_current_user_id` → `extract_token` (header bearer wins, else cookie) → `decode_access_token` (rejects revoked + non-`default` scopes).

### 3.2 New endpoint: `POST /api/v1/auth/demo-login`
- **Router:** add to `backend/app/api/auth.py` (same file as `login`).
- **Public**, **no request body** (demo credentials live server-side; never shipped to client).
- **Rate-limited** `@limiter.limit("10/minute")` (mirror `login`).
- **Gate:** if `settings.ALLOW_DEMO_LOGIN` is false → `raise HTTPException(403, "demo login is disabled")` (mirror the first-admin "disabled" pattern at `auth.py:84-96`).
- **Behavior (lazy seed):**
  1. Query `Organization` by `slug="helix-demo"`. If missing **or** empty (e.g. no projects) → call `demo_seed.seed_demo_org(db)` (idempotent).
  2. Resolve the demo `User` by reserved email `demo@helix.local` (confirm one active membership in the demo org).
  3. `token = create_access_token(str(demo_user.id), extra_claims={"demo": True})` — keep `scope="default"` so all downstream auth works unchanged; `demo` claim is for audit + optional UI affordance (UI demo-ness should still be driven by the org/flag, not solely the claim).
  4. `_set_auth_cookie(response, request, token)`.
  5. `write_audit(db, demo_org_id, demo_user_id, "demo_login", "user", demo_user_id, request=request)`.
  6. Return `{"access_token": token, "token_type": "bearer"}` (same shape as `login` for SDK/CLI parity).
- **Defense:** the demo account should be **blocked from `/auth/login`** by password (set an unusable/random password hash so it can only be reached via the gated demo endpoint). Document this in the seeder.
- **Do NOT** reuse `superadmin/impersonate` (requires a super-admin caller, 15-min imp token).

### 3.3 Frontend "Login with Demo User" button
- **Where:** `frontend/src/app/login/page.tsx`. Render the button **only when** `process.env.NEXT_PUBLIC_DEMO_ENABLED === "true"` (build-time baked).
- **Action:** POST `/api/v1/auth/demo-login` with `credentials:"include"` (same-origin via Next proxy), then call the existing `auth-context` flow: `refreshUser()` → `router.push("/dashboard")`. Reuse `loginFn` semantics (`auth-context.tsx:68-84`); the button is cosmetic — the real gate is the backend flag.
- **Cookie/role/tenant recap for demo:** identical HttpOnly SameSite=Strict cookie; role = `viewer` (read-only); tenant = the one demo org via `_active_membership`.

### 3.4 Env flag
- Backend `config.py`: add field `ALLOW_DEMO_LOGIN: bool = False`. (Because Settings uses `extra=ignore`, the env var is only honored once the field is declared — verified.)
- `.env` / `.env.example`: add `ALLOW_DEMO_LOGIN=false` and `NEXT_PUBLIC_DEMO_ENABLED=false`.
- `docker-compose.build.yml`: add `NEXT_PUBLIC_DEMO_ENABLED` as a frontend **build arg** (and frontend image env). Default false everywhere so existing deploys are unaffected.
- **Never** branch demo behavior on `APP_ENV`.

---

## 4. Access Control & Data Isolation

### 4.1 Real users never see demo data
- Mechanism: every list/detail endpoint resolves org via `get_current_organization_id` and filters by it. Confirmed broad org-scoping (projects, dashboard, sprints, agent_workflows, artifacts, cutovers, knowledge, usage, validation, recon). A real user in org A receives only org-A rows.
- **Requirement on the demo design:** the demo org must **never** be added as a membership to any real user, and the demo user must **never** be `is_super_admin=True` (super admins bypass org scoping in `user_has_permission`/`user_has_role`, `dependencies.py:71,81`, and can list all orgs via `/superadmin/*`).

### 4.2 Demo never touches real data
- Demo user has **exactly one** active membership (the demo org). `_active_membership` uses `.first()` **with no ORDER BY** (nondeterministic on multiple memberships) — so the single-membership invariant is mandatory. Encode this as a test (Track 3).

### 4.3 Per-router org-scope verification (acceptance gate during implementation)
- For every **new** demo-feature endpoint added in §6 (dashboard aggregations, recon list/summary, validation org list, etc.): it **must** depend on `get_current_organization_id` and filter by it — never query unscoped. Add this to the code-review checklist.
- **Known acceptable exposure:** super admins WILL see the demo org in `/superadmin/organizations` and platform stat counts. Documented, acceptable. The `/admin/*` (super-admin) surface is **not part of the demo nav** — the read-only demo user will 403 there (see §7 nav handling).

### 4.4 RBAC for the demo role
- Assign the demo user the existing **`viewer`** role (`auth_service.SYSTEM_ROLES["viewer"] = ["project:read","admin:audit:read"]`), seeded by `seed_roles()`. This naturally 403s all mutations. (If audit visibility is undesirable for demo, define a custom `demo_viewer` role with just `project:read`.)

---

## 5. Backend Demo-Data Strategy + Database Structure

### 5.1 Schema change: `organizations.is_demo`
- Add `is_demo = Column(Boolean, nullable=False, server_default=false)` to `Organization` in `backend/app/models/identity.py`.
- **Alembic migration** (DDL only): new revision, `down_revision = "v3w4x5y6z7a8"` (current head). Adds the `is_demo` column with server default false. **No data migration** — bulk demo content is NOT an Alembic migration (too large, JSON-heavy, needs reset/refresh).

### 5.2 Idempotent seeder: `app/services/demo_seed.py`
Model on `sprint_seed.py` (wipe-by-scope then insert; `db.flush()` between parent/child).
- **Entry point:** `seed_demo_org(db) -> dict` (returns counts + duration, like `seed_sprints_for_project`).
- **Constants:** fixed `DEMO_ORG_SLUG="helix-demo"`, `DEMO_USER_EMAIL="demo@helix.local"`, a **greppable sentinel** baked into names/descriptions (e.g. `"[HELIX-DEMO]"`) so isolation tests are exact and the CI grep gate can confirm the sentinel never appears in frontend source.
- **Clean phase:** delete all rows `WHERE organization_id = DEMO_ORG_ID` in **reverse FK order** (children first), then re-insert — so re-seed is deterministic and never touches real tenants.

### 5.3 FK insertion order (must satisfy NOT NULL + FKs)
`organizations → permissions (seed_permissions) → roles (seed_roles) → users → organization_members → projects (owner_id NOT NULL = demo user) → migration_requirements (source_text NOT NULL) → source_connections/target_connections (org+project+name+connector_type NOT NULL) → schemas → tables → columns (data_type NOT NULL) → llm_providers (provider_type,name,default_model NOT NULL) → llm_provider_secrets/llm_agent_mappings → workflow_runs (workflow_id UNIQUE, mode NOT NULL) → workflow_steps (UNIQUE(run_id,step_order)) → llm_usage_records (references step_id → create steps first) → validation_rules → validation_runs (started_by NOT NULL) → validation_results → recon_runs → recon_results → code_artifacts (filename,file_type,storage_path,content_hash NOT NULL) → code_artifact_versions → code_reviews/artifact_approvals → migration_cutovers (source_ref,target_ref NOT NULL) → source_schema_snapshots (payload,taken_at NOT NULL) → knowledge_docs (content NOT NULL) → llm_usage_records/org_cost_limits → sprint_* (reuse seed_sprints_for_project) → audit_logs (LAST, via write_audit)`.
- **WorkflowRun.workflow_id** is globally UNIQUE → namespace as `"demo-" + uuid` and wipe prior demo runs in the clean phase.
- **WorkflowStep** number 1..13 per run (UNIQUE(run_id, step_order)).

### 5.4 Per-model seed list (make every page production-real)
| Model | Demo rows |
|---|---|
| projects | 1 primary "Oracle GL → Snowflake Migration" (active, risk high, db). 1 completed + 1 draft secondary so list/status/risk filters show variety. |
| migration_requirements | 4–6 realistic `source_text` rows. |
| source/target_connections | 1 Oracle source + 1 Snowflake target, written via `project_service.add_source/add_target` (encryption + masking via `_encrypt_config`; never plaintext to `encrypted_config`). Use allowlist-safe fake hosts (`oracle-demo.internal`). |
| schemas/tables/columns | GL_LEDGER / GL_TRANS / GL_RECON with ~dozen columns + `row_count`. |
| workflow_runs (3–4) | 1 `completed` full 13-node BMAD run, 1 `running`, 1 `failed`. Each with `workflow_steps` (agent_name, step_order 1..13, status mix, `parsed_output`, `artifact_path`, provider/model, started/completed). **All `completed` runs replay via SSE with no worker.** |
| workflow_steps token fields | per-step `input_tokens/output_tokens/cost_usd` so the /agents token card is real (see §6 token gap). |
| llm_usage_records | one per step (tokens + `cost_usd`, provider, model, agent, step_id) so spend + usage pages populate. |
| org_cost_limits | 1 daily/monthly cap row so guardrail UI populates. |
| validation_rules (5–8) | mixed `rule_type`. validation_runs + validation_results with realistic pass/warn/**fail** mix (≥1 fail/warn so demo isn't suspiciously perfect). |
| recon_runs + recon_results | some `mismatch_count==0` (clean), some `>0` → believable <100% recon score with real mismatches. |
| code_artifacts + versions + code_reviews + artifact_approvals | Snowflake DDL, migrate.py, a rollback script (`rollback_artifact_id`), one ai_review, one pending + one approved approval. |
| migration_cutovers | 1 mid-window row (e.g. `state="diff"` + `diff_summary`). |
| source_schema_snapshots | 2 snapshots (drift diff has something to compare). |
| knowledge_docs | 3–5 runbooks for RAG/search. |
| sprint_* | reuse `seed_sprints_for_project` verbatim. |
| audit_logs | ~12 events (project_created, workflow_started, artifact_approved, demo_login…) via `write_audit` **last** so the HMAC chain + `/audit-logs/verify` stay valid. |

**Cross-page consistency:** keep numbers internally consistent (release `validation_score` vs actual results; recon scores vs recon_results) so dashboard/validation/recon agree.

### 5.5 Encryption + audit-chain rules (verified constraints)
- Connector configs: call `project_service.add_source/add_target` (or `_encrypt_config` directly) — Fernet-seals `encrypted_config` and sets `config_masked`. LLM secrets via `llm_provider_service.create_provider` / `encrypt_extra_config`. One active DEK per org (partial-unique index).
- Audit rows **only** via `write_audit` (per-org `pg_advisory_xact_lock`, chains `entry_hash` to prev; `metadata` column is NOT NULL → stores `'{}'`). Write **after** all other rows so the chain verifies.

### 5.6 Seeder invocation surfaces
1. **CLI** `python -m app.cli.seed_demo` (+ `--reset` = wipe-by-demo-org then re-seed). Mirror `scripts/seed.py` / `app/cli/rotate.py` style. For ops/first-deploy after `alembic upgrade head`.
2. **Lazy on first demo-login** (§3.2): `seed_demo_org` runs if the demo org is missing/empty.
3. **(Optional) compose one-shot** guarded by `ALLOW_DEMO_LOGIN`, run after migrations on the demo deploy.
- **Reset/refresh** = delete `WHERE organization_id = DEMO_ORG_ID` (children first) then re-seed — exactly the `sprint_seed._seed_clean` approach.

---

## 6. API Contracts: Endpoints to ADD / FIX

> All **new** list endpoints standardize on the `PaginatedResponse` envelope `{items,total,limit,offset}` (`backend/app/schemas/pagination.py`) and ISO-8601 timestamps; frontend uses `unwrapItems()` uniformly. All new endpoints depend on `get_current_organization_id`.

### 6.1 Bug fixes (do first — cheap, high-value)
| # | Fix | Where |
|---|---|---|
| B1 | Change fetch URL `/api/v1/admin/users` → `/api/v1/superadmin/users`; verify response keys map to `{id,email,name,role,is_active,created_at}` (adapt if different). Wire "Invite User" → `POST /api/v1/invitations`. | `frontend/src/app/admin/users/page.tsx:29` |
| B2 | Wire `runTest()` → `POST /api/v1/connectors/test {connector_type, config}`; render `result.success/message`; delete `setTimeout`/`Math.random` (line 439) + all hardcoded check strings (451-503) + literal banners (863, 910). Make form fields **controlled**. Wire Save → `POST /api/v1/projects/{id}/sources|targets` (project-scoped persistence; see decision below). | `frontend/src/app/connectors/page.tsx:436-441,451-503,863,910,975` |

### 6.2 New backend endpoints (org-wide aggregations & reads)
| Module | Method + Path | Exists? | Request | Response shape |
|---|---|---|---|---|
| Dashboard throughput | `GET /api/v1/dashboard/throughput?range=7\|30\|90` | **ADD** | range query | `[{label,completed,in_progress}]` |
| Dashboard activity | `GET /api/v1/dashboard/activity?limit=N` | **ADD** (or aggregate workflow_steps) | limit | `[{t,agent,kind,msg,workflow_id,project_id}]` |
| Dashboard agent-roster | `GET /api/v1/dashboard/agent-roster` | **ADD** | — | `[{name,role,provider,model,success_rate,runs,trend[]}]` (derive from workflow_steps + usage) |
| Dashboard connector-health | `GET /api/v1/dashboard/connector-health` | **ADD** | — | `[{name,instances,status,p95_latency_ms}]` |
| Dashboard risk-matrix | `GET /api/v1/dashboard/risk-matrix` | **ADD** | — | 3×3 counts |
| Dashboard projects-at-risk | `GET /api/v1/dashboard/projects-at-risk` | **ADD** | — | enriched `ProjectResponse` + `{owner_name,risk_score,validation_pct,recon_pct,source,target,updated_at}` (ProjectResponse lacks scores/owner_name — verified) |
| Dashboard validation-outcomes | `GET /api/v1/dashboard/validation-outcomes?window=24h` | **ADD** (or extend `/dashboard/stats`) | window | `{passed,warnings,failed,pass_rate}` |
| Agents pipeline detail | `GET /api/v1/agent-workflows/{id}` | **EXISTS** | — | `WorkflowDetail{...,steps:[{agent_name,step_order,status,parsed_output,artifact_path,provider_name,model_name,error_message,created_at}]}` |
| Agents artifacts | `GET /api/v1/agent-workflows/{id}/artifacts` | **EXISTS** | — | artifact list |
| Agents token usage | `GET /api/v1/agent-workflows/{id}/token-usage` **or** extend step rows with `{input_tokens,output_tokens,cost_usd}` | **ADD** (usage/llm by_agent is cost-only — insufficient) | — | `{total_tokens,total_cost_usd,by_agent:[{agent,tokens,cost_usd}]}` |
| Recon org list | `GET /api/v1/recon-runs` (org-wide) | **ADD** (curl 404) | filters/pagination | `[{id,project_id,table,source,target,source_count,target_count,mismatched,score,status,started_at}]` |
| Recon detail | `GET /api/v1/recon-runs/{run_id}` | **ADD** | — | run + `results[{table,category,mismatch_count,...}]` |
| Recon summary | `GET /api/v1/recon-runs/summary` | **ADD** | — | `{recon_score,matched,mismatched_pct,missing,avg_row_score}` (5 metric cards) |
| Recon trend | `GET /api/v1/recon-runs/trend?days=14` | **ADD** | days | time series |
| Recon run (action) | `POST /api/v1/projects/{id}/recon-runs` | **EXISTS** (`validation.py:174`) | — | run result (read-only demo: disabled) |
| Validation org rules | `GET /api/v1/validation-rules` (org-wide, enriched) | **ADD** (curl 404) | filters/pagination | `[{id,name,rule_type,source_ref,target_ref,status,owner_name,last_run_at,last_result}]` |
| Validation runs list | `GET /api/v1/projects/{id}/validation-runs` (currently single-GET only) | **ADD list** | pagination | `[{id,status,started_at,pass/warn/fail counts}]` |
| Validation type summary | `GET /api/v1/validation-runs/summary` | **ADD** | — | per-type `{row_count,schema,null,duplicate,distribution,business_rule}->{passed,warning,failed}` |
| Validation trend | `GET /api/v1/validation-runs/trend?days=14` | **ADD** | days | time series |
| Admin overview | `GET /api/v1/admin/overview` (single round-trip) **or** reuse 4 existing | **ADD (recommended)** | — | `{user_count,llm_provider_count,system_status,audit_events_per_day}` |
| Audit filters | extend `GET /api/v1/audit-logs` with `action,status,entity_type,q,from,to,limit,offset`; resolve `actor_id→actor_name`; add `status`/outcome; have `/export/csv` accept same filters | **EXTEND** (`audit.py:194-213`, limit-only today) | filters | `{items:[{id,action,actor_name,entity_type,entity_id,status,ip_address,created_at}],total,...}` |
| Approval queue (optional) | `GET /api/v1/agent-workflows?status=awaiting_approval` (add filter) | **ADD filter** | status | filtered run list |
| Approval actions | `POST /api/v1/agent-workflows/{id}/signal-approve \| /signal-reject` | **EXISTS** | — | (Temporal-dependent → disabled in read-only demo) |

### 6.3 Connectors Save model — DECISION
Choose **(a) project-scoped Save** to avoid a new table: the standalone `/connectors` page becomes project-aware and Save calls `POST /api/v1/projects/{id}/sources|targets` (exists, persists `ConnectionResponse{...,config_masked}`). The demo seed attaches the Oracle source + Snowflake target to the demo project so the page shows real rows and Test returns a real backend verdict. Heed the SSRF allowlist (`_enforce_host_allowlist`) — demo configs must point at allowlist-safe/seeded hosts. (Option (b), a new org-level `/api/v1/connections` store, is deferred.)

---

## 7. Frontend Integration & Migration

### 7.1 Removal checklist (file → const → replacement)
> Rule: **delete a mock const and rewire its JSX consumer in the same edit**, then typecheck/build. After a page is fully wired, **remove its `<DemoBanner>`** and fabricated consts together.

**`frontend/src/app/dashboard/page.tsx`** (lines 54-109 consts, 234-278 literals)
- `TREND_DATA` (54-65) + headline `1,247` (234) + `▲18.4%` (235) → `GET /dashboard/throughput`; AppShell metric string (142) → derive from `DashboardStats`.
- Validation donut literals (250-278: `92.4%`, `1862/312/167`) → `GET /dashboard/validation-outcomes` (or extend `/dashboard/stats`).
- `AGENT_EVENTS` (67-77) + Live chip → `GET /dashboard/activity` (or workflow SSE). Remove "Live" chip until backed by real stream.
- `AGENT_ROSTER` (79-86) → `GET /dashboard/agent-roster` (+ `GET /llm-agent-mappings`). Remove sparkline arrays.
- `PROJECTS_AT_RISK` (88-94) → `GET /dashboard/projects-at-risk`. Remove fake owners/IDs/timestamps.
- `CONNECTOR_HEALTH` (96-103) + `18 ACTIVE` (501) → `GET /dashboard/connector-health` (+ `/connectors/registry`). `RISK_GRID` (105-109) → `GET /dashboard/risk-matrix`.

**`frontend/src/app/agents/page.tsx`** (62-93 consts)
- `BMAD_PIPELINE` (62-76) → `GET /agent-workflows/{id}` steps + `/artifacts`; SSE `/stream` for live.
- **Fix LinearView bug**: sidebar maps `WORKFLOW_RUNS` at line 230 → must map the real `displayRuns`/`runs` prop.
- `WORKFLOW_RUNS` (78-85) fallback → `EmptyState` (real users see no fake runs).
- `TOKEN_USAGE` (87-93) + `42,308`/`USD 4.82` (322-324,686-688) → `GET /agent-workflows/{id}/token-usage`. `PHASE_GROUPS` (95-103) = static config, keep.
- Hardcoded title `Oracle GL → Snowflake` (266,552) → real project name.

**`frontend/src/app/reconciliation/page.tsx`** (28-31 empty arrays, 60-64 `0%` cards) → bind 5 metric cards to `GET /recon-runs/summary`, table to `GET /recon-runs`, donut/top-anomalies to `GET /recon-runs/{id}`, trend to `GET /recon-runs/trend`. Remove DemoBanner. (Read-only demo: "Run Reconciliation" disabled.)

**`frontend/src/app/validation/page.tsx`** (62-106 consts)
- `VALIDATION_CHECKS` (62-73) → `GET /validation-rules` (org). `TYPE_BREAKDOWN` (82-89) → `GET /validation-runs/summary`. `RECON_TREND` (91-106) → `GET /recon-runs/trend` (note this chart is recon-domain). Replace `92.4` fallback (189), `3 rules failing across 2 projects` (274), and 70/20/10 bar widths (154-156) with computed values.

**`frontend/src/app/admin/page.tsx`** (49-52 literals: `24`/`7`/`OK`/`1.2K` + fake sparks) → `GET /admin/overview` (preferred) or wire to `superadmin/users`, `llm-providers`, `system/health`, `audit-logs`. Keep `TILES` (static nav config).

**`frontend/src/app/approval/page.tsx`** (10-25 `APPROVAL_CONTEXT` + MockPage literals) — **DECISION: delete `/approval`** (it is a self-labeled design exploration; real approval lives inline on `projects/[id]/agents` via signal-approve/reject). Remove from nav. (Alternative if a queue is desired later: rebuild as `GET /agent-workflows?status=awaiting_approval`.)

**`frontend/src/app/developer-workspace/page.tsx`** (root IDE; 38-81 ARTIFACT_TREE, 91-95 VERSION_HISTORY, 103-129 DIFF_LINES, 140-170 AI_REVIEWS, 180-181 + 327-338 + 388-389 literals) — **DECISION: redirect root `/developer-workspace` → project picker** (it is project-agnostic, has no real data source). The real workspace is `projects/[id]/developer-workspace`. Delete the four arrays + literals.

**`frontend/src/features/developer-workspace/VersionHistoryDrawer.tsx`** (3-6 fake `versions`) — orphan (not imported). **DECISION: delete the file.** (If ever wired: `GET /artifacts/{id}/versions`.)

**`frontend/src/app/projects/[id]/agents/page.tsx`** (18-28 `DEMO_FLOW`, 123 `Untitled project`, 167-173 unwired Approve/Reject) → `DEMO_FLOW` → `EmptyState` (or real 13-node template). Wire Approve/Reject → `POST /agent-workflows/{id}/signal-approve|signal-reject` (disabled in read-only demo). Project name → `GET /projects/{id}`.

**`frontend/src/app/projects/[id]/developer-workspace/page.tsx`** (46 fallback fileList, 49 name, 81-85 versions, 96-110 static pyodbc/helix diff) → remove static diff snippets (they show even for real projects); render real artifact content via artifact-content endpoint; fallback fileList + versions → `EmptyState`; real project name.

**`frontend/src/app/projects/[id]/page.tsx`** (114-124 `DEFAULT_PHASES`) — **Low priority.** If backend reliably returns phases, drop the fallback + show `EmptyState`; otherwise ensure it cannot imply progress (all `pending`, progress 0).

**Out of scope (do not touch):** `app/page.tsx:490` (public marketing landing), `workflows/[id]/replay/page.tsx:27` AGENT_CODES (static config), `setup/first-admin` placeholder text, `/files /reports /plugins /templates` honest EmptyState stubs.

### 7.2 Dead buttons (95/217) — grouped by priority
- **P0 (correctness, ship in bug-fix milestone):** Connectors Test + Save (B2); Invite User (B1 → `POST /invitations`).
- **P1 (core demo surfaces):** Reconciliation "Run Reconciliation" (wire to `POST /projects/{id}/recon-runs`; **disabled in read-only demo**); Validation "New rule" → `POST .../validation-rules`, "Run all" → `POST .../validation-runs` (disabled in demo); Approve/Reject on `projects/[id]/agents` → signal endpoints (disabled in demo).
- **P2 (filters/export):** Audit filter chips + search + CSV/PDF export → after audit-filter endpoint extension.
- **P3 (cosmetic/empty stubs):** buttons on EmptyState stub pages — leave as no-ops or hide.
- **Demo-mode rule:** any button whose endpoint mutates state or needs Temporal must be **disabled with a "Read-only demo" tooltip** when the session is demo (derive from a `GET /auth/me`-exposed `is_demo`/org flag — add to `UserResponse` if needed).

---

## 8. State Management, Env Handling, Edge Cases

### 8.1 Per-page state contract (uniform)
For every page newly wired to real APIs:
1. **loading** → skeleton.
2. **success + empty** → explicit `EmptyState` (real new orgs are legitimately empty; demo org is seeded rich).
3. **401** → redirect to `/login` (centralize in `handleResponse`/`use-api.ts:27-38` or a shared wrapper — today it just throws, never redirects).
4. **403/404/5xx** → inline `ErrorBanner`.
Remove `<DemoBanner>` only when (1)–(4) are in place and the page is fully API-backed. `DemoBanner` presence is the canonical "still fake" signal for the CI gate.

### 8.2 Env handling
- Backend: `ALLOW_DEMO_LOGIN: bool = False` (config.py). Passed via existing `env_file` (covers backend+worker).
- Frontend: `NEXT_PUBLIC_DEMO_ENABLED` is **build-time baked** (only `NEXT_PUBLIC_*` consumed) — adding it requires a **frontend rebuild**. Add to `docker-compose.build.yml` build args.
- **Same-origin mandatory:** leave `NEXT_PUBLIC_API_URL` empty so the browser hits `/api/*` through the Next proxy (`next.config.mjs:8-13`) — keeps the HttpOnly SameSite=Strict cookie first-party. A cross-origin API URL **breaks** the cookie and CORS (`allow_credentials=True` forbids `*`). If a new demo domain is used, add the exact origin to `CORS_ORIGINS` (never `*`).
- **Memory note:** there is a pending `.env` revert + frontend rebuild (helix-env-revert-localhost) — fold the rebuild into this work.

### 8.3 Build-break risks
- Removing a top-level mock const without removing its JSX consumer is a build/runtime break (pages map over the consts in render). Always co-edit + run `npm run build`/typecheck.

### 8.4 Demo-specific edge cases
- **No worker for demo:** seed workflow_runs as `completed` (SSE emits `done` on first tick, no Temporal). Start/signal-approve/replay would hang on `Client.connect` (or raise in prod APP_ENV) — so in demo mode **disable** those buttons (read-only role already 403s mutations; UI disable prevents confusing errors).
- **SSE works for demo:** demo cookie is the normal `helix_token`; `/auth/sse-ticket` is org-agnostic → tickets mint fine.
- **No global auth guard:** no `middleware.ts`, no `RequireAuth`. Each newly-fetching page must independently handle unauthenticated (per §8.1 step 3), else a logged-out hit throws a raw error instead of redirecting.
- **List-envelope inconsistency:** newer pages (validation, connectors, admin/users) assume bare arrays and will break on enveloped responses. Standardize new endpoints on `PaginatedResponse` and make the frontend uniformly `unwrapItems()`.

---

## 9. Testing & Validation Strategy

> Build on the existing substrate: 288 pytest fns / 51 files (`backend/tests`, real `helix_test` Postgres, Redis mocked, rate-limit disabled, SETUP_TOKEN injected) + 4 Playwright specs (`frontend/e2e`). No Jest/Vitest — stay on pytest + Playwright.

- **Track 1 — Per-page smoke (44 routes):** Playwright, authenticated as the **demo** user. Per route assert: 200/no `/login` redirect; zero console/pageerror; zero failed `/api/*` (except known-empty 404s); ≥1 real row rendered **AND `<DemoBanner>` ABSENT**. Generate the route list by glob of `frontend/src/app/**/page.tsx`; CI diffs discovered routes vs a checked-in manifest (fails on drift). Resolve dynamic `[id]` from `GET /projects`, `/agent-workflows`, `/artifacts`.
- **Track 2 — Demo-login e2e** (`e2e/demo-login.spec.ts`): real browser context (cookies). `goto /login` → click "Login with Demo User" → assert `context.cookies()` has `helix_token` → expect `/dashboard` → walk every Sidebar nav route by **clicking links** (also validates nav wiring) → each: real seeded rows + no DemoBanner. Reload → identical row counts (determinism). Skip gracefully if `/auth/demo-login` returns 404 (demo disabled). MUST run same-origin via the Next proxy (cookie auth).
- **Track 3 — Real-user isolation:** Backend `test_demo_isolation.py` — fresh admin+org via `first-admin`, seed demo into the demo org, assert the real admin's `/projects`, `/agent-workflows`, `/dashboard/stats`, `/knowledge/docs`, `/sprints`, `/artifacts`, `/usage/llm` return **zero** demo rows; assert a real session calling `/auth/demo-login` does not merge orgs; assert single-membership invariant for the demo user. Frontend `e2e/real-user-isolation.spec.ts` — real login walks 44 routes, asserts the demo **sentinel string** (`[HELIX-DEMO]`) never appears.
- **Track 4 — Contract tests:** `test_auth_demo_login.py` + `test_demo_seed.py`, modeled on `test_api_contract_*.py` + the sprint-seed test. Assert: demo-login 200 + `Set-Cookie helix_token` (HttpOnly, SameSite=strict, Path=/) from the raw header; subsequent `/auth/me` returns demo user; idempotency (double-call → equal `COUNT(*)` per demo table); demo-login is **public** (no SETUP_TOKEN) but rate-limited; new list endpoints keep `{items,total,limit,offset}` + ISO-8601 (reuse `_is_iso`, `_is_paginated_envelope`).
- **Track 5 — Regression:** full 288-test pytest suite green before+after (gate). Add: (a) `GET /api/v1/superadmin/users` exists (never 404), document `/admin/users` invalid; (b) `connectors.spec.ts` intercepts `page.route` and asserts Test click issues a real `POST /connectors/test` (no Math.random) and Save issues a real persist POST. Keep auth/dashboard/llm-settings/workflow-smoke specs; update workflow-smoke's localStorage token-plant note (auth is cookie-only — token-planting won't work; use real demo-login).
- **Track 6 — No-mock CI grep gate:** `scripts/check_no_mock.sh` (ripgrep + small reviewed allowlist), run in CI **and** as a `.pre-commit-config.yaml` local hook. Fails on, under `frontend/src/{app,features}`: (a) `<DemoBanner` usages/imports; (b) `MOCK_|SAMPLE_|FAKE_DATA|DEMO_FLOW` mock-data arrays; (c) `Math.random()` inside connector/test handlers / setTimeout-as-network; (d) the seed sentinel leaking into source. Allow skeleton/empty-state components, the `/login` demo-button copy, and test files. Add the Track-1 route-manifest diff check here too.
- **CI runner (greenfield):** create `.github/workflows/ci.yml` (no app CI exists today): job 1 backend pytest vs Postgres+Redis services (`helix_test`, env mirroring conftest); job 2 frontend `npm run lint` + `npm run build`; job 3 Playwright vs built app + live backend (pin a CI compose from `docker-compose.dev.yml`; `PLAYWRIGHT_BASE_URL` = frontend origin, never backend); job 4 grep gate + route-manifest diff.

---

## 10. Phased Rollout Plan + Migration/Validation Checklist

### Milestone 0 — Foundation (schema + flags + seeder) — *no UI change*
1. Add `organizations.is_demo` to `models/identity.py` + Alembic migration (`down_revision="v3w4x5y6z7a8"`, DDL only).
2. Add `ALLOW_DEMO_LOGIN: bool=False` to `config.py`; add `ALLOW_DEMO_LOGIN`, `NEXT_PUBLIC_DEMO_ENABLED` to `.env`/`.env.example` + `docker-compose.build.yml` build args.
3. Build `app/services/demo_seed.py` (idempotent, FK-ordered, sentinel-tagged, encryption + audit via helpers) + CLI `app/cli/seed_demo.py` (`--reset`).
4. Tests: `test_demo_seed.py` (idempotency, FK integrity, audit-chain verify, encryption masking).
> **Dependency:** nothing. **Gate:** seeder double-run → equal counts; `/audit-logs/verify` ok.

### Milestone 1 — Demo login (backend + button) — *depends on M0*
1. `POST /api/v1/auth/demo-login` (gated, lazy-seed, same cookie, audited) in `auth.py`.
2. `login/page.tsx` button behind `NEXT_PUBLIC_DEMO_ENABLED`; reuse auth-context flow; same-origin.
3. Expose `is_demo` on `/auth/me` `UserResponse` for UI affordances.
4. Tests: `test_auth_demo_login.py` (cookie attrs, idempotency, rate-limit, public); `e2e/demo-login.spec.ts`; `test_demo_isolation.py`.
> **Gate:** demo login → `/dashboard`; isolation tests pass; real-user sees no demo rows.

### Milestone 2 — Bug fixes (fast wins) — *parallelizable with M3*
1. B1 `/admin/users` path fix + Invite wiring.
2. B2 connectors real Test + Save (project-scoped) + controlled fields; remove all fake strings.
3. Tests: superadmin/users-not-404 regression; `connectors.spec.ts` network-intercept.
> **Gate:** Track-5 regression specs pass.

### Milestone 3 — Backend aggregation endpoints — *depends on M0 (seed data to test against)*
1. Dashboard: throughput, activity, agent-roster, connector-health, risk-matrix, projects-at-risk, validation-outcomes.
2. Recon org reads: list, detail, summary, trend.
3. Validation org reads: org rules list, runs list, type summary, trend.
4. Agents: per-workflow token-usage (or step token fields).
5. Audit filters + actor-name resolution + filtered CSV.
6. Admin overview (single round-trip).
7. Contract tests for each (envelope + ISO-8601, org-scope).
> **Dependency:** M0 (seeded rows). **Gate:** each endpoint returns rich data for demo org, empty for fresh org.

### Milestone 4 — Frontend de-mock (page by page) — *depends on M3 per-page*
Order by user-visibility & dependency:
1. `/dashboard` (consumes M3 dashboard endpoints) — remove 6 consts + literals.
2. `/agents` (workflow detail/steps/token-usage) — remove BMAD_PIPELINE/WORKFLOW_RUNS/TOKEN_USAGE + fix LinearView line-230 bug.
3. `/validation` + `/reconciliation` (M3 validation/recon reads).
4. `/admin` home (admin/overview).
5. `projects/[id]/agents` + `projects/[id]/developer-workspace` (EmptyState fallbacks, real content/diff, signal wiring).
6. Deletions/redirects: delete `/approval`, redirect root `/developer-workspace`, delete `VersionHistoryDrawer.tsx`.
7. `projects/[id]` DEFAULT_PHASES (low priority).
After each page: remove DemoBanner + consts in the same edit; `npm run build`; per-page state contract (§8.1).
> **Gate:** Track-1 smoke per page (no DemoBanner, real rows); typecheck/build green.

### Milestone 5 — Dead-button wiring — *interleaved with M2/M4*
P0→P3 per §7.2; demo-mode disable rule for mutating/Temporal buttons.

### Milestone 6 — CI + final hardening — *depends on M1–M4*
1. `.github/workflows/ci.yml` (4 jobs) + `scripts/check_no_mock.sh` + pre-commit hook + route manifest.
2. Full Track 1–6 run green.
3. Frontend rebuild with `NEXT_PUBLIC_DEMO_ENABLED` (folds in the pending `.env` revert+rebuild memory note).
> **Gate:** grep gate passes (zero DemoBanner/mock consts/Math.random in connector handlers/sentinel); 288 pytest + all e2e green.

### Final migration/validation checklist (nothing breaks)
- [ ] `alembic upgrade head` adds `is_demo`; existing rows default false; no data loss.
- [ ] `ALLOW_DEMO_LOGIN=false` on existing/prod deploys → `/auth/demo-login` 403; no behavior change.
- [ ] APP_ENV untouched (Temporal enforcement, cookie Secure, SSRF allowlist intact).
- [ ] Demo deploy stays same-origin (`NEXT_PUBLIC_API_URL` empty); cookie sent; CORS not `*`.
- [ ] Demo user: `is_super_admin=False`, exactly one active membership, read-only role, password unusable via `/auth/login`.
- [ ] Seeder idempotent (double-run equal counts); reset = delete-by-demo-org + re-seed; audit chain verifies.
- [ ] Real org A: `/projects`, `/dashboard/stats`, `/agent-workflows`, `/usage/llm`, `/sprints`, `/artifacts`, `/knowledge` return zero demo rows (sentinel absent).
- [ ] Fresh real org renders EmptyStates, not fabricated rows.
- [ ] Every removed mock const has its JSX consumer rewired in the same commit; `npm run build` passes.
- [ ] No `<DemoBanner>` / `MOCK_/SAMPLE_/FAKE_DATA/DEMO_FLOW` / connector `Math.random` remain in `frontend/src/{app,features}` (grep gate).
- [ ] `/admin/users` → `/superadmin/users`; connectors Test/Save issue real POSTs (network-intercept verified).
- [ ] 288 pytest + Playwright (smoke, demo-login, isolation, contract, regression) green in CI.
