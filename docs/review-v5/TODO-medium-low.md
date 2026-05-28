# Outstanding TODOs — review-v5 (MEDIUM / LOW + deferred HIGH)

Per the review rules, only CRITICAL and HIGH were auto-fixed. Everything below is
logged for later. Full context (exploit scenarios, suggested fixes) lives in the
source reports: `security-review.md`, `code-audit.md`, `ui-ux-review.md`.

## Deferred HIGH (too large or needs a decision)

- **SC-013 (HIGH, partially mitigated)** — SSE ticket replay window. The ticket is
  *already* session-bound (revoked on logout/refresh, 60s TTL), which covers most
  of the risk. Remaining hardening (bind to caller IP/UA) is deferred because
  reliable IP binding requires trusted-proxy `X-Forwarded-For` parsing first
  (see SC-051) — behind Caddy, `request.client.host` is always loopback.
  Proper fix: implement SC-051, then bind the ticket to forwarded IP + UA hash.
- **UI-016 (HIGH, deferred)** — Replace hundreds of inline `style={{}}` pixel
  literals in `developer-workspace/page.tsx`, `setup/first-admin/page.tsx`,
  `connectors/page.tsx`, `approval/page.tsx` with Tailwind utilities + CSS tokens
  so user font/density/dark-mode tweaks propagate. Est. 1–1.5 days; mechanical
  but large. Adopt a lint rule (`no inline style`) afterward.
- **SC-010 follow-on (optional)** — The robust fix is `HttpOnly; Secure;
  SameSite=Strict` cookies issued by the backend (eliminates XSS token theft
  entirely). We shipped the lower-risk alternative (client logout now revokes
  server-side). Cookie migration is an architecture change — needs sign-off.

## Security — MEDIUM (from security-review.md)

- **SC-030** — ENCRYPTION_KEY rotation must rewrap all legacy secrets; add
  `POST /admin/secrets/rewrap-all`. `secret_service.py:41-53`
- **SC-031** — `event_metadata` not covered by audit HMAC; strip `\r\n\x00` from
  audit string columns; include `sha256(event_metadata)` in entry hash. `audit.py:30-39,108-115`
- **SC-032** — Replace `"platform"` sentinel org id with a fixed UUID or separate
  super-admin audit table. `superadmin.py:31`
- **SC-033** — Slack signature should HMAC raw bytes, not `decode(errors="replace")`. `integrations.py:62`
- **SC-034** — Refuse to start temporal-ui when bound off-loopback with auth
  disabled. `docker-compose.yml:119-148`
- **SC-035** — Drop `allow_credentials=True` (API is bearer-only). `main.py:164-181`
- **SC-036** — Enforce `scope` claim centrally in `get_current_user_id` so SSE
  tickets can't act as full bearers for 60s. `jwt.py:282-287`
- **SC-037** — Add dummy bcrypt burn on the inactive-user branch of password reset. `password_reset_service.py:41-49`
- **SC-038** — Join webhook deliveries to endpoint org for defence-in-depth. `webhooks.py:133-171`
- **SC-039** — `config_masked` leaks last 4 chars of secrets; return `"***"`. `project_service.py:89-97`
- **SC-040** — Disable gzip on `/auth/*` and `/llm-providers/*` (BREACH). `main.py:183`
- **SC-041** — Cap multipart file *count*, not just total body size. `main.py:120-142`, `artifacts.py:88-103`

## Security — LOW

- **SC-050** revocation negcache 1s leak; **SC-051** audit/ratelimit IP uses
  proxy loopback — parse trusted `X-Forwarded-For` (blocks SC-013 hardening);
  **SC-052** checksum vendored BMAD scripts before subprocess; **SC-053**
  paginate `superadmin/users|organizations`; **SC-054** cap compliance bundle
  rows; **SC-055** fail Docker build when `requirements.lock` missing; **SC-056**
  bind `/metrics` to a private port; **SC-057** emit HSTS on any https scheme,
  not just `APP_ENV=production`.

## Code — MEDIUM (from code-audit.md)

- **M-001** invalidate prior password-reset tokens on new request. `password_reset_service.py:31-61`
- **M-002** `encrypt_value` falsy-value guard should be `is None or == ""`. `secret_service.py:56-62`
- **M-003** lower secret-detection length threshold; add `org-` pattern. `artifact_store.py:167-190`
- **M-004** non-numeric `expected` on a row_count rule should error, not pass. `validation_service.py:106-108`
- **M-005** move `try/except` inside the CDC per-cutover loop. `cdc_engine.py:46-53`
- **M-006** explicit `db.flush()` before reading `user.id`. `auth_service.py:71-81`
- **M-007** custom connectors report empty capabilities → all buttons greyed. `connector_service.py:86-94`
- **M-008** S3 schema inference reads only 4096 bytes (truncates wide headers). `connectors/s3/connector.py:110-122`
- **M-009** connectors leak SQLAlchemy engines/pools (no caching/dispose). postgres/mysql/sqlserver/snowflake connectors
- **M-010** per-node artifact paths collide on shared agent codes; key by step. `bmad_per_node_workflow.py:159-162`
- **M-011** canonicalise (`realpath`) artifact paths before allowlist compare. `agent_workflows.py:207-219`
- **M-012** invitation re-invite with different role silently keeps old role. `invitation_service.py:43-53`
- **M-013** validate LLM token budget ≥ 4000 at config load. `bmad_executor.py:67-74,216-218`
- **M-014** burndown if/else has identical branches; future days should be flat/None. `sprint_service.py:339`
- **M-015** recon `mismatch_count` may overflow Integer; use BigInteger. `recon_service.py:53-66`
- **M-016** SSE could emit typed `event:` lines (optional). `agent_workflows.py:303-333`
- **M-017** two parallel frontend API clients (`client.ts` vs `use-api.ts`) — consolidate.
- **M-018** validate/quote `domain` before interpolating into CORS list literal. `cli/__main__.py:248-260`
- **M-019** share a module-level ThreadPoolExecutor across activities. `bmad_node_activities.py:126-133`

## Code — LOW

- **L-001** use `model_json_schema()` not `str(annotation)` in prompts; **L-002**
  consistent `mask_key`; **L-003** `group_by` label non-portable to SQLite;
  **L-004** migrate to FastAPI `lifespan`; **L-005** parallelise webhook delivery;
  **L-006** count CSV rows without loading whole file; **L-007** log dropped
  frontmatter keys; **L-008** optional tiktoken token estimate; **L-009** CLI
  surface subprocess returncode/stderr; **L-010** narrow JSON-parse except in SDK;
  **L-011** cross-tab token sync via `storage` event; **L-012** real 404 on the
  marketing site instead of redirect-to-home.

## UI/UX — MEDIUM (from ui-ux-review.md)

- **UI-018** divider reflow after grid fix (done partially — verify). 
- **UI-019** unify Avatar size API (keyword vs numeric).
- **UI-020** drop redundant `outline-none` where `focus-ring` already sets it.
- **UI-021** wire ⌘K / ⌘J shortcuts or hide the `<Kbd>` hints; Bell is a no-op.
- **UI-022 / UI-029 / UI-033** bump `text-ink-4` 10.5px informational text to `text-ink-3`/11.5px.
- **UI-023** differentiate the two "Close navigation" labels in the mobile drawer.
- **UI-024** persist first-admin wizard step/draft to sessionStorage.
- **UI-025** add `truncate min-w-0` to metric cell values post-reflow.
- **UI-026** extract a shared `<SearchInput>` primitive (4+ variants today).
- **UI-027** add `max-h-[85vh] overflow-y-auto` to Modal content for mobile.
- **UI-028** `flex-wrap` the `/projects` filter bar; scroll the tab strip.
- **UI-030** WorkspaceSwitcher / UserFooter look clickable but have no menu.
- **UI-031** clamp the validation hero `text-[56px]` number.
- **UI-032** enlarge dense-table icon link touch targets to ≥44px.
- **UI-034** disable the New Project Cancel link while submitting.
- **UI-035** add a DemoBanner to the mock `/approval` page.

## UI/UX — LOW

- **UI-036** login "Forgot?" `href="#"` dead link; **UI-037** lazy-load dashboard
  charts; **UI-038** move font from CSS `@import` to `next/font`; **UI-039**
  export explicit `viewport`; **UI-040/044** centralise relative-time/i18n
  formatting; **UI-041** bind the sidebar "All systems operational" dot to real
  health; **UI-042** add roadmap links on stub pages; **UI-043** reserve `pulse`
  for actively-running items; **UI-045** swap raw palette for tokens on
  reconciliation; **UI-046** add a `<Skeleton>` primitive to cut CLS.

## Cross-cutting follow-ups surfaced during fixing

- **Monolithic workflow gap (C-002)** — the worker-side terminal-state reconcile
  was added to `BMADPerNodeWorkflow` only. `BMADPlanningWorkflow` (monolith) still
  doesn't reconcile `WorkflowRun.status`. Add the same terminal activity there if
  that path is exercised in production.
- **Pre-existing test failures (34)** — unrelated to this branch (verified against
  the pristine tree): schema-from-models FK drift, unavailable connectors in the
  sandbox, prior pagination-envelope assertion drift, and a few stale test imports.
  Worth a separate cleanup pass.
- **SC-015 connector-side** — `?hostaddr=` driver arg not added in `connectors/`
  (config-level host-pin covers current connectors; add if a connector ever
  re-resolves the hostname internally).
- **E2E** — the Playwright setup-flow test (if any) must now supply a setup token;
  not run here (needs full stack).
