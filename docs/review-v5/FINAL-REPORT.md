# Helix AI Migration — Full Codebase Review & Fix (review-v5)

Branch: `upgrade/review-and-fix`. Nothing committed yet (working tree only).
Reviewed by 3 parallel agents; fixed by 3 parallel agents + manual integration pass.

## Headline numbers

- **131 findings** total — Security 33, Code 52, UI/UX 46.
- **51 CRITICAL/HIGH** targeted for auto-fix.
- **49 fully fixed**, **2 deferred** (SC-013 hardening — already session-bound; UI-016 inline-style refactor).
- **80 MEDIUM/LOW** logged in `TODO-medium-low.md`.
- **78 files modified, +1832 / −355**, plus 4 new files, 2 deleted.

## Files changed (81 code files, by area)

- **backend (48)** — routers, services, schemas, auth/jwt, ssrf, rate_limiting, config, 1 model, conftest + 15 test files, + new `security/password_policy.py`, new Alembic migration `s0t1u2v3w4x5_review_v5_*`, + 2 new tests.
- **frontend (20)** — dashboard, projects, sprints (page/analytics/risks/timeline), admin (page/users/system-health), agents, connectors, reconciliation, validation, developer-workspace, setup/first-admin, `components/ui/Card.tsx`, `components/layout/PageHero.tsx`, `lib/use-api.ts`, `lib/api/client.ts`, `lib/auth-context.tsx` + new `app/loading.tsx`, `app/error.tsx`, `app/not-found.tsx`.
- **worker (3)** — `main.py`, `workflows/bmad_per_node_workflow.py`, `activities/bmad_node_activities.py`.
- **agents (2)** — `runtime/providers/bedrock_provider.py`, `runtime/bmad_executor.py`.
- **connectors (1)** — `s3/connector.py`.
- **sdk (2)** — `python/helix_sdk/client.py`, `typescript/src/index.ts`.
- **scripts (2)** — `generate-secrets.sh`, `generate-secrets.ps1`.
- **root (3)** — `.env` (deleted), `backend/test.db` (deleted), `.gitignore` (already covered).

## Bugs fixed by severity

### CRITICAL code (4/4)
- **C-001** duplicate `workflow_run` rows → upsert (FOR UPDATE) + unique index.
- **C-002** Temporal runs never reconciled → new `persist_workflow_terminal_state_activity` updates status on every workflow exit (per-node).
- **C-003** envelope double-decrypt race → return plaintext from probe, decrypt once.
- **C-004** CDC engine corrupting `diff_summary` → tolerant reader; all writers consistent.

### HIGH code (17/17)
H-001 sprint-index race (FOR UPDATE + partial unique + retry) · H-002 recon no longer re-raises after commit · H-003 SSE revalidates token exp · H-004 daily-cost window off-by-one · H-005 KEK degrades to legacy on bad key shape · H-006 Bedrock Llama-3+ chat template · H-007 BMAD step failure now fails the workflow · H-008 seed_roles refreshes system-role perms · H-009 marketplace `kind` enum-validated · H-010 story_points NULL coalesce · H-011 SDK `list_all()`/`listAll()` paginators · H-012 per-agent LLM routing threaded through PydanticAI path · H-013 S3 client cached + actionable creds error · H-014 webhook empty-events guard · H-015 `/approve` signals Temporal before DB · H-016 sprint task status `Literal` · H-017 `use-api`/`client` 204 guard.

## Security issues resolved

### CRITICAL (3/3)
- **SC-001** rate limiter now ON by default (`HELIX_DISABLE_RATE_LIMIT` opt-out for tests).
- **SC-002** password policy (min 12 / complexity / common-denylist) on all set-password schemas + the setup-wizard client check.
- **SC-003** `.env` and `backend/test.db` deleted; secret-gen scripts refuse to clobber placeholder `.env`.

### HIGH (9 fixed / 1 deferred)
- **SC-010** logout now revokes server-side (alt to HttpOnly cookies — see TODO).
- **SC-011** `/auth/first-admin` requires `X-Setup-Token`; **setup wizard updated** to collect + send it (otherwise onboarding would break).
- **SC-012** impersonator id threaded JWT→audit→HMAC chain (+ migration column).
- **SC-014** artifact-content paths hard-pinned under canonical roots.
- **SC-015** SSRF: resolved-IP pinned at admission; flag re-read per call.
- **SC-016** ILIKE `% _ \` escaping + `ESCAPE` clause.
- **SC-017** literal IPv6 / decimal / IPv4-mapped IP parsing before DNS.
- **SC-018** uniform `/readyz` body (no DB-state leak).
- **SC-019** length caps on free-text fields flowing into LLM prompts.
- **SC-013 (deferred)** — ticket is already session-bound (revoked on logout, 60s TTL). Full IP/UA binding needs trusted-proxy `X-Forwarded-For` (SC-051) first; behind Caddy a raw IP bind is loopback-useless.

## UI/UX issues fixed (CRITICAL 3/3, HIGH 13/14)

- **UI-001/UI-018** responsive metric strips (`grid-cols-2 sm:3 lg:5/6`) + reflowing dividers on dashboard/projects/3 sprint pages.
- **UI-002** dev-workspace IDE: `overflow-x-auto`, `min-w-0`, collapsible side panes with accessible toggles.
- **UI-003** risks two-col grid gated to `xl:`.
- **UI-004** 5 dead admin tiles → non-navigable "Coming soon" chips.
- **UI-005** new `loading.tsx` / `error.tsx` / `not-found.tsx`.
- **UI-006** PageHero responsive padding; **UI-007** dashboard chart rows reflow.
- **UI-008/009/010** aria-labels + focus-ring on inputs and icon-only buttons.
- **UI-011** reconciliation: demo banner + disabled CTA; **UI-012** validation demo data gated behind `hasProjects`.
- **UI-013** timeline SVG viewBox-scaled; **UI-014** `Card.title` → `<h2>` (with `as` prop); **UI-015** admin tables wrapped in `overflow-x-auto`; **UI-017** reconciliation token colors.
- **UI-016 (deferred)** — large inline-style→token refactor (~1–1.5 days).

## Lighthouse

**Not run** — per your decision (would require installing `lighthouse` + a production build/serve). Static perf findings stand in:
- **UI-038** render-blocking font via CSS `@import` → move to `next/font`.
- **UI-037** charts bundled into every dashboard load → lazy-load.
- **UI-039** no explicit `viewport` export.
- No CSP on the Next app (marketing site has one).

## Outstanding TODOs

Full list in `TODO-medium-low.md`: **2 deferred HIGH** (SC-013, UI-016), **49 MEDIUM**, **31 LOW**, plus cross-cutting follow-ups:
- Monolithic `BMADPlanningWorkflow` still lacks terminal-state reconcile (per-node done).
- 34 pre-existing test failures (verified unrelated to this branch) need a cleanup pass.
- SC-015 connector-side `?hostaddr=` not added (config host-pin covers current connectors).
- E2E setup-flow test must now supply a setup token (not run here).

## Verification performed

- All 41 changed Python files `py_compile` clean.
- `frontend tsc --noEmit` clean (incl. my SC-010/SC-011 edits).
- Backend: new + directly-affected tests 50 passed / 0 failed; full suite 273 passed / 34 failed (all 34 pre-existing, confirmed via `git stash` against pristine tree).
- Agents provider-adapter tests: 14 passed (incl. Bedrock template branches).
- Confirmed `.env` + `test.db` deleted; migration is a clean new head; both workflows + the new activity registered in `worker/main.py`.
- Test files inspected for gutting: only legitimate adaptations (password length, setup-token header, recon 422 status) — no skips/xfails/weakened asserts added.

## Constraints honored

No framework/language switch, no URL or response-schema changes (additive only), no new runtime dependencies. The two architectural items (HttpOnly-cookie auth, SSE fetch-streaming) were flagged for your decision and replaced with in-scope alternatives.
