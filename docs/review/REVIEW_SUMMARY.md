# Helix Migration — Code Review Summary

> Generated 2026-05-26 against `main` at commit `4de7eb0e`.
> Aggregates 4 deep-dives + 1 architecture map. Each file below has its own line-by-line review.

## Files in this folder

| File | LOC | Scope |
|---|---|---|
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | 252 | Whole-project module map + dataflow + tech stack |
| [`REVIEW_BACKEND.md`](./REVIEW_BACKEND.md) | 1272 | `backend/` + `connectors/` (~165 files) |
| [`REVIEW_FRONTEND.md`](./REVIEW_FRONTEND.md) | 965 | `frontend/src/` (~106 files) |
| [`REVIEW_AGENTS_WORKER.md`](./REVIEW_AGENTS_WORKER.md) | 675 | `agents/` + `worker/` + `_bmad/scripts/` (~48 files) |
| [`REVIEW_WEBSITE.md`](./REVIEW_WEBSITE.md) | 1741 | `website/` public marketing site |
| **Total** | **~4900 lines** | |

## Aggregate severity counts

| Area | 🔴 CRITICAL | 🟠 HIGH | 🟡 MED | 🔵 LOW | Total |
|---|---:|---:|---:|---:|---:|
| Backend + connectors | 3 | 41 | 95+ | 25+ | ~164 |
| Frontend | 14 | 25 | 89 | 60 | 188 |
| Agents + worker | 0 | 7 | 13 | ~110 | ~130 |
| Website | 1 | 13 | 33 | 62 | 109 |
| **Repo total** | **18** | **86** | **230+** | **257+** | **~591** |

> Severity definitions (consistent across the 4 reports):
> - 🔴 **CRITICAL** — exploitable security flaw, data corruption, or shipping behaviour visibly wrong to real users
> - 🟠 **HIGH** — security/data risk under non-trivial preconditions, broken contract, or significant UX bug
> - 🟡 **MED** — correctness gap, missing test, fragile code, accessibility miss
> - 🔵 **LOW** — nit, polish, style, optional optimisation

## All 🔴 CRITICAL findings at a glance

### Backend (3)
1. **`backend/app/core/config.py:16,28,30`** — JWT_SECRET_KEY / encryption keys ship with `"change_me"` default. If `APP_ENV != production` is set anywhere, prod can boot with a known secret.
2. **`backend/connectors/sqlserver/connector.py:44`** — `trust_cert = "no" if ... else "no"` — both branches identical. Self-signed cert paths can't connect to SQL Server.
3. **`backend/app/api/audit.py:30`** — `AUDIT_HMAC_KEY` reuses `JWT_SECRET_KEY` as fallback. Any JWT-key rotation invalidates the audit chain HMAC.

### Frontend (14, summary)
- 6 pages render fully-styled mock data with NO indicator that it's mock (`/dashboard`, `/agents`, `/validation`, `/projects/[id]/agents`, `/projects/[id]/developer-workspace`, `/developer-workspace`).
- `admin/users/page.tsx:44` + `audit-logs/page.tsx:42` — `data = users.length > 0 ? users : DEMO` fallback shows fictional users in prod when DB is empty.
- `lib/sprints/api.ts:441` — JWT in EventSource URL query string (leaks into logs).
- `components/layout/Sidebar.tsx:140-151` — sidebar hard-codes "Avery Johnson · Platform Admin".
- `components/icons/AppIcon.tsx:13` + `LLMIcon.tsx:11` — `import * as si from "simple-icons"` bundles 2-3 MB of unused icons.
- `admin/system-health/page.tsx:28` — backend/frontend shape mismatch; page renders nothing.

### Agents + worker (0)
No critical findings. 7 HIGH (Gemini key in URL query, Vertex `init` global state race, Bedrock empty key validation, etc.).

### Website (1)
- `public/helix-console-demo.html` — 1.5 MB Figma-bundler blob served unmodified at `/helix-console-demo.html`. `<meta name="robots" content="noindex">` missing. Recommend rasterising to PNG + keeping interactive demo behind opt-in.

## Top 25 prioritised fixes across the repo

> Rank = highest expected impact ÷ effort. Read each per-file review for full context.

| # | Area | File:line | Action | Severity |
|---|---|---|---|---|
| 1 | Backend | `app/core/config.py:16,28,30` | Replace `"change_me"` JWT/encryption defaults with `secrets.token_hex(32)` factories; fail-closed when defaults ship outside prod | 🔴 |
| 2 | Frontend | `admin/users/page.tsx:44`, `audit-logs/page.tsx:42` | Drop demo-data fallback; show real empty state | 🔴 |
| 3 | Agents | `runtime/pydantic_ai_client.py:76-101` | Stop writing API keys to `os.environ`; use explicit provider constructors | 🟠 |
| 4 | Agents | `runtime/providers/gemini_provider.py:28` | Move Gemini key from `?key=` URL to `x-goog-api-key` header | 🟠 |
| 5 | Frontend | `lib/sprints/api.ts:441` | Stop passing JWT in EventSource URL query string; use short-lived SSE token | 🔴 |
| 6 | Backend | `app/services/llm_provider_service.py:91` | `rotated_at=uuid.uuid4()` is wrong type (writes UUID into timestamp) | 🟠 |
| 7 | Backend | `connectors/sqlserver/connector.py:44` | Fix `trust_cert = "no" if ... else "no"` typo | 🔴 |
| 8 | Frontend | `components/layout/Sidebar.tsx:140-151` | Wire `UserFooter` to `useAuth().user` (was hard-coded) | 🔴 |
| 9 | Backend | `app/api/audit.py:30 + 43-63` | Separate `AUDIT_HMAC_KEY` from `JWT_SECRET_KEY`; advisory-lock chain writes per-org | 🔴 |
| 10 | Frontend | `components/icons/{AppIcon,LLMIcon}.tsx:11-13` | Per-icon imports from simple-icons; drop ~2-3 MB | 🔴 |
| 11 | Backend | `app/api/superadmin.py:73-92` | Embed `imp_by` in impersonation JWT, audit every super-admin action | 🟠 |
| 12 | Website | `public/helix-console-demo.html` | Rasterise to PNG (~150 KB) + add `noindex`; keep interactive behind opt-in | 🔴 |
| 13 | Backend | `app/api/webhooks.py` | SSRF guard on webhook URL registration + delivery | 🟠 |
| 14 | Agents | `runtime/bmad_executor.py:355-399` + `llm_client.py:26` | Use worker-local SessionLocal when running inside an activity | 🟠 |
| 15 | Backend | `app/services/validation_service.py:59-138` + `recon_service.py:39-50` | Open new SessionLocal in background tasks (request session is closed) | 🟠 |
| 16 | Frontend | `app/setup/first-admin/page.tsx:329` | Replace direct `localStorage.setItem` with `setupFirstAdmin()` from AuthContext | 🟠 |
| 17 | Worker | `activities/bmad_node_activities.py:302-329` | Add idempotency upsert on `(workflow_run_id, step_order)` | 🟠 |
| 18 | Website | `index.html:23, 27` + `public/og-image.svg` | Rasterise OG image to PNG (SVG rejected by most social crawlers) | 🟠 |
| 19 | Frontend | `components/TweaksPanel.tsx` + all modals | Add focus trap + `role="dialog"` + `aria-modal`; ship a `<Modal>` primitive | 🟠 |
| 20 | Worker | `workflows/bmad_per_node_workflow.py:159-162` | Catch `asyncio.TimeoutError` on approval wait; return `status="expired"` | 🟠 |
| 21 | Backend | `app/services/workflow_service.py:83-89` | Wrap `helix.run()` in `asyncio.to_thread(...)` so local fallback doesn't block event loop | 🟠 |
| 22 | Backend | all `connectors/*/connector.py` | Declared `async` but body is sync SQLAlchemy — wrap with `asyncio.to_thread` | 🟠 |
| 23 | Backend | `app/services/secret_service.py:14` | Handle empty `api_key` (Bedrock/Vertex IAM auth) without raising | 🟠 |
| 24 | Frontend | `lib/auth-context.tsx:60-62` + `login/page.tsx` | Call `/auth/me` after login to fetch the real user name (today: `email.split("@")[0]`) | 🟠 |
| 25 | Website | `public/sitemap.xml` | Expand to include all 21 `/docs/{id}` URLs (generate from `docs-content.ts` at build) | 🟠 |

## Cross-cutting themes

### Mock / demo data still lurking in production paths
- Frontend admin pages fall back to demo arrays when DB is empty.
- Six product pages render mock data with no banner.
- Sidebar user identity hard-coded.
- Website demo HTML is a 1.5 MB Figma bundle.

This is the single biggest reputational risk — operators standing up Helix for the first time see fabricated content presented as real.

### Auth + secrets
- JWT signing key has a known `"change_me"` default.
- Audit HMAC reuses JWT key as fallback.
- Gemini provider leaks API key in URL.
- PydanticAI adapter writes provider API keys to `os.environ` (concurrent race).
- EventSource SSE auth passes JWT in URL query (logs leak).

### Cross-tenant isolation
Generally solid — `resolve_active_org_id` is consistently used after the audit-LOWs fix landed (`a74ba13c`). Per-route audit confirms zero remaining ad-hoc lookups in backend.

### Sync-in-async
- Connectors declared `async` but body uses sync SQLAlchemy.
- Backend's local fallback for HelixBMAD calls `.run()` synchronously inside an async route.
- Worker per-node activities use sync DB commits.
Net effect: under load the event loop is blocked. Not a correctness bug — a throughput cliff.

### Test coverage
- Backend: tests exist for auth, encryption, sprints (extended), connectors (extended), agent workflows. Missing: webhooks, audit chain HMAC verification, validation service, recon service.
- Frontend: zero unit tests (Playwright dep listed in `package.json` but no specs).
- Agents: 9 test files (~857 LOC) — solid coverage on `static_analysis`, sparser on `bmad_executor` edge cases. No per-provider adapter tests.
- Website: no tests.

### Bundle / performance
- Frontend `dist/`: ~325 kB JS / 33 kB CSS gz (acceptable).
- Website `dist/`: ~255 kB JS / 25 kB CSS gz (good).
- 1.5 MB demo HTML served from `public/` (NOT counted in the SPA bundle; visitors only pay when they click View Demo).
- `simple-icons` star-imports drag in 2-3 MB unused (per-icon import gets it back).

## Suggested next sprint focus

Three workstreams in priority order. Each is sized for ~1 week of focused work.

### Workstream A — security hardening (week 1)
Closes items 1, 3, 4, 5, 9, 13 from the top-25 plus the SSRF + secret-rotation cluster. Output: `app/core/config.py` no longer ships with weak defaults; HMAC chain has its own key; SSE auth uses short-lived token; webhooks have SSRF guard. Run `bandit` over `backend/` + `agents/` once those land.

### Workstream B — "no mock data in product" (week 2)
Items 2, 8, 10, 16, 24. Plus the 6 product pages with unmarked mock content. Goal: every product page either renders real backend data or renders an explicit empty state. Sidebar shows the real logged-in user. Settings name → backend `/auth/me`.

### Workstream C — runtime correctness + tests (week 3)
Items 6, 14, 15, 17, 20, 21, 22, 23. Plus expand backend tests to webhooks + audit + validation + recon services. Add Playwright smoke covering login → create project → start workflow → approve → view artifacts. Add adapter unit tests for all 10 LLM providers (currently zero).

## How to consume this report

1. **Skim this file** for the severity matrix + cross-cutting themes.
2. **Read [`ARCHITECTURE.md`](./ARCHITECTURE.md)** if you're new to the codebase — it's a 252-line orientation.
3. **Open the per-area review** (`REVIEW_BACKEND.md`, `REVIEW_FRONTEND.md`, etc.) for the file you're touching. Each is structured: high-level architecture → file-by-file with severity-tagged findings → cross-cutting → top-10 → architecture suggestions.
4. **Use the severity emoji** to triage: 🔴 ship-blocker, 🟠 fix-this-quarter, 🟡 backlog, 🔵 nice-to-have.

All four per-area reviews follow the same shape, so flipping between them is consistent.

---

*End of summary.*
