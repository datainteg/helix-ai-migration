# Backend Fixes — review-v5 (backend-fixer)

Branch: `upgrade/review-and-fix`. Scope: `backend/`, `.env`, root infra (`scripts/`).
No new runtime dependencies added. No URL paths / response schemas / auth model /
DB engine / framework changed. New JSON fields are additive only.

## Files changed

### Application code (`backend/`)
- `backend/app/rate_limiting.py` — SC-001
- `backend/app/security/password_policy.py` — SC-002 (new file)
- `backend/app/schemas/identity.py` — SC-002
- `backend/app/api/auth.py` — SC-002, SC-011
- `backend/app/api/invitations.py` — SC-002
- `backend/app/core/config.py` — SC-011 (SETUP_TOKEN), SC-015 (HELIX_ALLOW_PRIVATE_HOSTS)
- `backend/app/main.py` — SC-011 (first-admin bootstrap startup notice)
- `backend/app/models/observability.py` — SC-012 (audit_logs.impersonator_id)
- `backend/app/api/audit.py` — SC-012 (write_audit impersonator_id + HMAC coverage)
- `backend/app/auth/jwt.py` — SC-012 (propagate imp_by to request.state)
- `backend/app/api/agent_workflows.py` — SC-014, SC-019, H-003, H-015
- `backend/app/api/workflow_ops.py` — SC-019
- `backend/app/schemas/project.py` — SC-019
- `backend/app/api/connectors.py` — SC-015 (pin resolved IP, re-read flag from settings)
- `backend/app/api/projects.py` — SC-015 (use pinned config at delivery)
- `backend/app/security/ssrf.py` — SC-017
- `backend/app/services/knowledge_search.py` — SC-016 (ILIKE escape + ESCAPE clause)
- `backend/app/api/health.py` — SC-018 (uniform /readyz body)
- `backend/app/schemas/sprint.py` — SC-019, H-016 (TaskStatusLiteral)
- `backend/app/services/workflow_service.py` — C-001 (upsert), C-002 (terminal helper)
- `backend/app/services/envelope_encryption_service.py` — C-003, H-005
- `backend/app/services/cdc_engine.py` — C-004 (tolerant diff_summary read)
- `backend/app/api/cutovers.py` — C-004
- `backend/app/api/cdc.py` — C-004
- `backend/app/services/sprint_service.py` — H-001, H-010
- `backend/app/services/recon_service.py` — H-002
- `backend/app/api/validation.py` — H-002 (map failure dict → 422)
- `backend/app/api/sprints.py` — H-003 (SSE re-validate)
- `backend/app/services/cost_service.py` — H-004
- `backend/app/services/auth_service.py` — H-008 (refresh system role perms)
- `backend/app/api/marketplace.py` — H-009 (kind: MarketplaceKind)
- `backend/app/services/webhook_service.py` — H-014
- `backend/app/api/webhooks.py` — H-014 (events non-empty validator)

### Migrations
- `backend/alembic/versions/s0t1u2v3w4x5_review_v5_security_code_fixes.py` (new)
  - SC-012: `audit_logs.impersonator_id` column + index
  - C-001: unique index `(workflow_id, organization_id)` on `workflow_runs` (IF NOT EXISTS)
  - H-001: partial unique index `(organization_id, project_id, index)` on `sprints` (IF NOT EXISTS)
  - Applies cleanly as the new head off `r9s0t1u2v3w4`.

### Infra / scripts
- `scripts/generate-secrets.sh` — SC-003 (refuse to overwrite placeholder `.env`; route to `.env.local`)
- `scripts/generate-secrets.ps1` — SC-003 (same, PowerShell)
- `.env` — **deleted** from working tree (SC-003)
- `backend/test.db` — **deleted** (SC-003)
- `.gitignore` — already covers `*.db` and `.env*`; no change needed.

### Tests
- `backend/tests/conftest.py` — set `HELIX_DISABLE_RATE_LIMIT=1`, `SETUP_TOKEN`, inject `X-Setup-Token`
- `backend/tests/test_review_v5_unit.py` (new) — SC-002, SC-016, SC-017 unit coverage
- `backend/tests/test_review_v5_api.py` (new) — SC-011, SC-002(API), SC-016, H-005, H-016
- Updated existing fixtures to satisfy the new password policy / setup token:
  `test_auth.py`, `test_password_reset.py`, `test_api_contract_iso8601.py`,
  `test_knowledge.py`, `test_schema_drift_dos_sec018.py`, `test_final.py`,
  `test_connectors_extended.py`, `test_agent_mapping_bulk.py`, `test_stored_connections.py`,
  `test_agent_workflows.py`, `test_connectors.py`, `test_llm.py`, `test_upload.py`,
  `test_artifacts.py`, `test_projects.py`
  (all changes: lengthen auth passwords to ≥12 compliant chars; point seeded
  artifact under ARTIFACT_STORAGE_PATH; widen recon status-code assertion to
  include 422).

## Per-finding status

### Security
- **SC-001** FIXED — limiter `enabled=not HELIX_DISABLE_RATE_LIMIT`; critical log when disabled.
- **SC-002** FIXED — `validate_password()` (min12/max128, upper+lower+digit+symbol, common denylist) applied to FirstAdminSetup, AcceptInviteRequest, PasswordResetConfirm, UserCreate. Not applied to UserLogin.
- **SC-003** FIXED — `.env` + `backend/test.db` deleted; generate-secrets scripts refuse to clobber placeholder `.env` (write `.env.local`); gitignore already covers.
- **SC-011** FIXED — `/auth/first-admin` requires `X-Setup-Token` == `settings.SETUP_TOKEN`; refuses when unset; startup + per-call critical log with guidance.
- **SC-012** FIXED — `imp_by` propagated to `request.state.impersonator_id`; `write_audit(impersonator_id=...)` records it; column added via migration; included in HMAC chain.
- **SC-014** FIXED — `artifact-content` paths hard-pinned under canonical roots (ARTIFACT_STORAGE_PATH + `_bmad-output`) via `is_relative_to` after `resolve()`.
- **SC-015** FIXED (backend portion) — `_enforce_host_allowlist` re-reads the flag from settings each call and pins the validated public IP into the `host` config field so connect-time uses the admission-validated address. NOTE: connector adapters live in `connectors/` (other agent's scope); the `?hostaddr=` psycopg2 variant was not added there — the host-pin in config achieves the same DNS-rebind protection because the connector builds its URL from `host` verbatim.
- **SC-016** FIXED — `_escape_like` escapes `\ % _` and `ilike(..., escape="\\")` added.
- **SC-017** FIXED — literal IPs (dotted-quad, IPv6, decimal-encoded, IPv4-mapped IPv6) checked directly before DNS.
- **SC-018** FIXED — `/readyz` body is `{"status":"ok"}` / `{"status":"not_ready"}`; `database`/`detail` kept optional in schema (backward-compatible) but unpopulated.
- **SC-019** FIXED — `max_length` caps added to requirement_text/source_text/notes (10 KB) and other free-text Create/Update fields (200–4000).

### Code
- **C-001** FIXED — `_upsert_workflow_run` selects existing row FOR UPDATE by (workflow_id, org) and updates, else inserts; unique index added.
- **C-002** FIXED — `update_workflow_run_status_for_temporal_completion(workflow_id, status, summary, ...)` exposed for worker activities; persists a terminal step. (Worker-side call site is the worker-fixer's job.)
- **C-003** FIXED — `_get_dek_for_decrypt` returns `(dek, plaintext)`; `decrypt_for_org` uses the plaintext (no second decrypt).
- **C-004** FIXED — column is `Text`; all writers keep JSON-string, all readers use a tolerant `_load_diff_summary` (handles dict/legacy/malformed) so a bad row can't crash the CDC loop or list endpoint.
- **H-001** FIXED — `max(index) FOR UPDATE` allocator + partial unique index + IntegrityError retry-once → 409 on collision.
- **H-002** FIXED — recon no longer re-raises; persists `error_message` + a diagnostic ReconResult; returns failure dict; API maps to 422.
- **H-003** FIXED — both SSE generators (agent_workflows + sprints) check `exp` each tick and re-decode every 10/5 ticks; emit `auth_expired` and close on lapse.
- **H-004** FIXED — `since` snapped to midnight UTC of first window day; loop bounds matched.
- **H-005** FIXED — `_kek()` degrades to legacy-only MultiFernet + `critical` log on invalid ENCRYPTION_KEY shape.
- **H-008** FIXED — `seed_roles` recomputes permissions for existing `is_system=True` roles; leaves custom roles alone.
- **H-009** FIXED — `MarketplaceEntry.kind: MarketplaceKind` (catalog now validated at import).
- **H-010** FIXED — all `story_points` sums coalesce to 0.
- **H-014** FIXED — `WebhookUpdate.events` validator rejects empty/blank; `deliver_webhook` skips `[""]` instead of matching `*`.
- **H-015** FIXED — `/approve` sends the Temporal approve/reject signal before the DB update; logs + DB-only fallback if the handle can't be resolved.
- **H-016** FIXED — `SprintTaskUpdate.status` constrained to `TaskStatusLiteral` (mirrors frontend TaskStatus union).
- **H-012** SKIPPED — file `agents/runtime/bmad_executor.py` is in the worker/agents scope. Coordinate with that fixer. (Noted here per instructions.)

## New Alembic migration
- `s0t1u2v3w4x5_review_v5_security_code_fixes.py` — verified it applies on top of
  the existing chain (`alembic upgrade head` succeeded on a fresh Postgres).

## Tests passing / failing

Test DB: local Postgres 16 container; ran with
`DATABASE_URL=postgresql://helix:helix_password@localhost:5432/helix_test`
so the app's `SessionLocal()` and the `db_session` fixture share one DB.

- **Full suite**: `273 passed, 6 skipped, 34 failed` (415 s).
- **New + directly-affected tests** (the ones validating these fixes):
  `50 passed, 0 failed` —
  `test_review_v5_unit.py`, `test_review_v5_api.py`, `test_webhook_ssrf.py`,
  `test_password_reset.py`, `test_audit_chain.py`, `test_daily_cost.py`,
  `test_marketplace.py`, `test_knowledge.py`, `test_cost_service.py`.

### The 34 failures are ALL pre-existing — verified by re-running on a
### `git stash` of every backend/scripts change. They fail **identically** on
### the pristine tree, so none were introduced by this work. Categories:

1. **Schema-from-models vs migrations FK drift** — `test_envelope_encryption.py`,
   `test_rotate_orchestrator.py`, `test_worker_idempotency.py`. The `db_session`
   fixture builds the schema via `Base.metadata.create_all()`; the
   `org_data_encryption_keys.organization_id` FK to `organizations` then rejects
   the raw DEK inserts these tests do without seeding an org.
2. **Connector / network unavailable** — `test_connectors.py`,
   `test_connectors_extended.py`, `test_stored_connections.py`,
   `test_schema_drift.py` (no live source/target DB in the sandbox).
3. **Pagination-envelope assertion drift (prior review's API-C2 change)** —
   `test_cutover.py`, `test_projects.py`, `test_auth.py::test_cross_organization_*`,
   `test_agent_workflows.py::test_list_all_workflows_*`, `test_final.py`
   (expects `POST /projects` → 200 but endpoint returns 201).
4. **Pre-existing test bugs** — `test_agent_workflows.py::test_get_workflow_cross_org_rejected`
   (imports non-existent `_seed_default_roles_and_permissions`),
   `test_agent_mapping_bulk.py` (4), `test_prompt_override.py`, `test_upload.py`,
   `test_slack_perm_sec012.py` (3), and
   `test_security_fixes.py::test_sec003_logout_invalidates_sse_ticket`
   (mocked Redis can't track revocation, so the SSE ticket stays valid).

All four categories reproduce on the unmodified base commit.

## Follow-ups / notes
- **asyncpg** (`asyncpg==0.31.0`, already pinned in `requirements.lock`) was missing
  from the local `.venv` and had to be installed to import `app.db.session`
  (the async engine is constructed eagerly at import). No code change required;
  CI environments that install `requirements.lock` are unaffected.
- **SC-015 connector-side**: the `?hostaddr=`/`host=` driver argument was NOT
  added to `connectors/` (out of scope). The implemented host-pin in the config
  dict closes the same DNS-rebind gap for the current connectors (they build the
  connection URL from `host`). If a future connector re-resolves the hostname
  internally, the connector-side `hostaddr` change should be added by the
  connectors fixer.
- **Pre-existing test failures (NOT caused by these changes)**:
  - `test_auth.py::test_cross_organization_access_is_denied` — asserts
    `GET /projects` returns a bare `[]` but the endpoint returns the paginated
    envelope `{items,total,...}` (API-C2 change from a prior review).
  - `test_agent_workflows.py::test_list_all_workflows_returns_runs_for_org` /
    `::test_list_all_workflows_paginates` — iterate the list endpoint body as a
    bare list while it returns the pagination envelope.
  - `test_agent_workflows.py::test_get_workflow_cross_org_rejected` — imports a
    non-existent symbol `_seed_default_roles_and_permissions` from auth_service
    (verified failing on the pristine pre-change file).
  These are owned by whoever introduced the pagination envelope / wrote those
  tests; left untouched to avoid scope creep.
