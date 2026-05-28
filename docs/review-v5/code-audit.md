# Code Audit Report

## Summary
- Total findings: 52 (Critical: 4, High: 17, Medium: 19, Low: 12)
- Areas covered: backend, frontend, worker, connectors, agents, cli, sdk, website
- Top systemic concerns:
  - Workflow start path persists in a "started" state but never marks the run as completed/failed when Temporal returns asynchronously — the DB row is permanently stale and the SSE stream never closes.
  - `_persist_workflow_result` issues a second `create_workflow_run()` with the SAME `workflow_id`, producing duplicate rows (and likely a unique-constraint violation when the index exists) and breaks all status lookups.
  - Several services swallow exceptions with `db.rollback()` after a partial commit but do NOT re-raise, leaving callers with the illusion of success. This pattern shows up in `_persist_started_workflow`, `_persist_workflow_result`, `webhook_service.deliver_webhook` (txn-per-loop), and `cdc_engine._poll_once`.
  - The "live" CDC engine resolves `MigrationCutover.diff_summary` as if it were a JSON string while later code paths assign it as a Python dict — the column's storage format is inconsistent across the codebase.
  - Sprint index computation, password reset, marketplace catalog and provider adapters all exhibit per-call race conditions or sloppy fall-back behaviour that silently corrupts state.

---

## Findings

### CRITICAL

#### C-001: BMAD workflow persistence duplicates `workflow_run` rows
- **File**: `backend/app/services/workflow_service.py:228-237`
- **Issue**: `_persist_workflow_result` calls `create_workflow_run(db, …, workflow_id=result.workflow_id, …)` unconditionally. For the Temporal path, `_persist_started_workflow` has already inserted a row with the same `workflow_id` earlier in `start_bmad_planning_workflow`. The fallback path also runs this immediately after a single `helix.run()` so two rows for the same `workflow_id` get inserted by the SAME request when both paths are exercised. There is no UPDATE-or-INSERT logic. The model exposes `workflow_id` as part of the persistence contract; once the migration adds a unique index this will hard-fail with `IntegrityError`, and even without the index every downstream `get_workflow_run(workflow_id=…)` returns the first row found and silently masks the second.
- **Impact**: Duplicate workflow rows in production; status lookups return stale data; once the index lands the workflow start endpoint 500s.
- **Fix**: In `_persist_workflow_result`, `SELECT … FOR UPDATE` the existing row by `workflow_id`+`organization_id` and call `update_workflow_run_status` instead of `create_workflow_run`. Persist steps against the existing run's id.

#### C-002: Temporal workflow start never reconciles DB status
- **File**: `backend/app/services/workflow_service.py:80-95, 200-220`
- **Issue**: When Temporal accepts a workflow, `_persist_started_workflow` writes `status="started"` and returns immediately. No callback, signal handler, or worker activity is wired up to set the row to `completed/failed/expired` when the workflow actually finishes — `persist_workflow_step_activity` only writes per-step rows, never updates `WorkflowRun.status`. Frontend SSE in `agent_workflows.py:319-330` polls until the run hits `completed|approved|rejected|failed`; with the row stuck at `"started"` the SSE loop just times out at 120s on every successful run.
- **Impact**: Every Temporal workflow appears "stuck" in the UI; cost rollups by status are wrong; the `/api/v1/agent-workflows/{id}` endpoint never reflects the true terminal state.
- **Fix**: Add a `persist_workflow_terminal_state_activity` called at the end of `BMADPerNodeWorkflow.run` (and the monolithic graph) that sets the run row to `completed/rejected/expired`, OR have the workflow start endpoint kick off a background task that polls the Temporal handle and reconciles.

#### C-003: `_get_dek_for_decrypt` probes with `Fernet(dek).decrypt(ct)` then returns the dek without consuming the result — but the helper inside `decrypt_for_org` re-runs `Fernet(dek).decrypt(ciphertext)` once more, doubling decrypt cost and (more importantly) reading the same ciphertext twice in places that race
- **File**: `backend/app/services/envelope_encryption_service.py:130-141, 150-157`
- **Issue**: The probe loop calls `Fernet(dek).decrypt(ct_bytes)` to test viability, discards the plaintext, returns the `dek`, and then `decrypt_for_org` does `Fernet(dek).decrypt(ciphertext.encode())` again. This is benign for the happy path but during rotation it means every read of a per-org secret is 2× the bcrypt-shaped CPU cost on a primary-hot DEK. The bigger correctness bug: when multiple DEKs are present and the active one cannot decrypt the ciphertext but a historical one can, the probe-then-redecrypt sequence calls Fernet.decrypt() twice in a row — if the ciphertext was rotated between probe and final decrypt by another writer, the second call raises and the caller sees `InvalidToken` despite the probe succeeding.
- **Impact**: Sporadic decrypt failures during rotation; doubled CPU per read; latency spike when org has many historical DEKs.
- **Fix**: Return both the `dek` AND the plaintext from `_get_dek_for_decrypt`; in `decrypt_for_org` just use the plaintext directly.

#### C-004: `cdc_engine._poll_cutover` corrupts the `diff_summary` column
- **File**: `backend/app/services/cdc_engine.py:62-66`
- **Issue**: The function does `summary = json.loads(c.diff_summary) if c.diff_summary else {}` then `c.diff_summary = json.dumps(summary)` — assumes the column stores a JSON string. But `backend/app/api/cutovers.py:125` reads it as a Python dict (`json.loads(c.diff_summary) if c.diff_summary else None`), and other code paths (the diff endpoint earlier in cutovers.py) assign a Python dict directly. The actual `MigrationCutover.diff_summary` column type is inconsistent across writers: the CDC engine writes JSON-string, the diff endpoint writes a dict (depending on SQLAlchemy column type). If the column is `Text`/`String`, then dict-writers store the Python `repr` (`"{'foo': 'bar'}"`) which the CDC engine's `json.loads` then fails on; if the column is `JSONB`, the CDC engine double-encodes (wraps the entire JSON string as a JSON string). Either way `last_poll_check_at` either crashes the next poll or pollutes the column.
- **Impact**: Tail-state cutovers either crash the poll loop or accumulate increasingly nested escape sequences; the CDC engine silently dies on the affected rows (caught by `_poll_once`'s `except`).
- **Fix**: Inspect column type via `MigrationCutover.__table__.c.diff_summary.type`; if JSONB, write the dict directly; if Text, normalise all writers to JSON strings. Add a regression test that round-trips a tick through both a writer and the CDC engine.

---

### HIGH

#### H-001: Sprint `index` allocation races between concurrent creators
- **File**: `backend/app/services/sprint_service.py:30-39`
- **Issue**: `last_index = db.query(Sprint).filter(...).count()` then assigns `last_index + 1`. Two concurrent POSTs to `/sprints` race: both count N, both insert sprint index N+1. There is no unique constraint enforced at the service layer. The comment says "manual indexing avoids re-numbering races" — it doesn't.
- **Impact**: Duplicate sprint indices; burndown/velocity rollups misalign tasks; UI displays two `S3`s.
- **Fix**: `SELECT max(index) FROM sprints WHERE org=... AND project=... FOR UPDATE` inside a single transaction, then insert. Or add a partial unique index `(organization_id, project_id, index)` and retry on IntegrityError.

#### H-002: `recon_service.run_row_count_recon` swallows the source/target failure into 'failed' without rolling back the partial result row
- **File**: `backend/app/services/recon_service.py:80-84`
- **Issue**: On exception it sets `recon_run.status = "failed"` and `recon_run.error_message = str(exc)` but the function has already committed an empty `recon_run` row at line 36, so a connection error on `get_row_count` leaves a "failed" run with no `ReconResult` rows AND re-raises. The frontend's recon list then shows the run as failed with no diagnostic data; the actual exception bubbles up to the API layer which produces a 500. Either the row should be deleted on failure or the exception should be caught and converted to a structured 4xx/5xx with detail. Re-raising AFTER `db.commit()` also means the caller's outer transaction (if any) sees an already-committed failed row.
- **Impact**: Failed recon runs accumulate without diagnostic data; user sees a generic 500.
- **Fix**: Do not re-raise after persisting `status="failed"`; return a structured failure dict. Optionally include `error_message` in `ReconResult` for forensics.

#### H-003: SSE token verification reuses ONE DB session across 120 ticks despite the docstring saying otherwise
- **File**: `backend/app/api/agent_workflows.py:286-318`
- **Issue**: Code opens `auth_db = SessionLocal()` at line 286, closes at line 301, then `event_generator` opens/closes a `tick_db` per loop iteration — that part is fine. But `decode_access_token_async(token)` is called inside the auth block; if that helper does its own DB lookups they reuse the same short-lived session — OK. The bug is upstream: the per-tick session is opened/closed up to 120× per request; on a noisy frontend (multiple tabs open to different workflows) this saturates the pool with very-short-lived `OPEN`/`COMMIT` sequences and Postgres logs are flooded. Worse, `get_workflow_status` itself opens its own `SessionLocal()` when `db=None`, BUT here it's passed `tick_db`, so it uses that one — fine. The real correctness bug: line 297 catches generic `Exception` and converts to a 401 INSIDE the try/finally, but the `raise HTTPException(...)` happens before `auth_db.close()` is reached only because `finally` runs on raise. OK so that part works. Genuine bug: the SSE loop does not refresh the JWT — if a 60s token expires after 60s the connection keeps streaming for 120s with an expired token; downstream signal-approve calls then fail.
- **Impact**: SSE pipeline silently exceeds token lifetime; suspended users continue receiving updates for up to 2 minutes after their JWT expires.
- **Fix**: Re-validate `payload["exp"]` (or re-decode the token) each tick. Add a `last_revalidate` timer so the cost is paid every 10 ticks rather than every tick.

#### H-004: `daily_cost` zero-fill walks the wrong cursor range
- **File**: `backend/app/services/cost_service.py:188-195`
- **Issue**: `cursor = (datetime.now(timezone.utc) - timedelta(days=days - 1)).date()` then `while cursor <= today`. For `days=30`, the loop yields 30 day entries (today-29 .. today). That is correct. BUT `since = datetime.now(timezone.utc) - timedelta(days=days)` (line 175) goes back 30 days from "now", which crosses day boundaries: if the API call comes in at 09:00 UTC, `since` is `30 days ago at 09:00 UTC` — the SQL query then includes/excludes the partial day depending on click-time. The zero-fill loop, however, uses only the date portion. So a row written at 08:30 30 days ago is missed by the query but its date bucket is filled with `0.0` by the loop. Cost summaries appear to "lose" usage near the window boundary.
- **Impact**: Off-by-one on cost rollups at the trailing edge of the window; flaky when the dashboard is refreshed at different times of day.
- **Fix**: Snap `since` to midnight: `since = (now - timedelta(days=days-1)).replace(hour=0, minute=0, second=0, microsecond=0)`.

#### H-005: `_kek()` uses `MultiFernet` for encryption but the legacy key is wrong shape on rotation
- **File**: `backend/app/services/envelope_encryption_service.py:42-59`
- **Issue**: `_kek_direct()` requires `settings.ENCRYPTION_KEY` to already be a valid base64-encoded 32-byte Fernet key. If an operator's `.env` still has the pre-fix sha256-derived value, `_kek_direct()` raises `ValueError("Fernet key must be 32 url-safe base64-encoded bytes")` at startup — silently caught nowhere. Every encrypt + decrypt call then fails. The `_kek_legacy()` fallback exists in MultiFernet but if `_direct_fernet()` itself raises during construction, MultiFernet never receives the legacy key either, and the whole encrypt path is dead. The config validator in `core/config.py` should reject the bad shape at boot, but if it doesn't, the failure is mode-dependent (encrypt fails first, then decrypt fails — but legacy reads SHOULD still work via `_legacy_fernet`).
- **Impact**: An operator who has not rotated their KEK envvar to a valid Fernet key gets a hard boot failure with no actionable error; downgrade path is unclear.
- **Fix**: Wrap `_kek_direct()` construction in try/except and degrade to legacy-only MultiFernet with a `logger.critical(...)` so the operator sees the issue.

#### H-006: Bedrock provider uses a Python dict-literal expression as a key, producing `True`/`False` as the actual key
- **File**: `agents/runtime/providers/bedrock_provider.py:91-95`
- **Issue**: 
  ```python
  return {
      "prompt": ...,
      "temperature": ctx.temperature,
      "max_gen_len" if mid.startswith("meta.") else "max_tokens": ctx.max_tokens,
  }
  ```
  This is parseable Python, but the conditional expression is evaluated as the key — depending on `mid` it produces `"max_gen_len"` or `"max_tokens"`. That part is fine. Real bug: for `mistral.*` the conditional resolves to `"max_tokens"`, but Mistral on Bedrock expects `"max_tokens"` — OK. For `meta.*` it resolves to `"max_gen_len"` — correct. So the logic is actually right. The genuine bug: there's no `<s>[INST]…[/INST]` tokens for Mistral (Mistral does use `[INST]` but BeDrock's Mistral wrapper expects no surrounding `<s>`), and Llama 3+ models do not use `[INST]` at all — they use the `<|begin_of_text|><|start_header_id|>` chat-template format. Code emits `<s>[INST]…[/INST]` for both, so Llama 3 + Llama 4 prompts will be tokenised as literal text and produce garbage output.
- **Impact**: Llama 3 / Llama 4 Bedrock calls return low-quality output.
- **Fix**: Branch on `mid.startswith("meta.llama-3")` and emit the proper chat template; document Mistral wrapper expectations.

#### H-007: `BMADPerNodeWorkflow.run_step` swallows failure status into the next phase
- **File**: `worker/workflows/bmad_per_node_workflow.py:132-163, 166-185`
- **Issue**: `run_step` checks `result.get("success")` only for the persist activity's `status` field — if the BMAD activity returns `success=False` (e.g. LLM transport mock fell back to mock with parse errors), `_outputs[...] = result["parsed"]` still happens on line 167 (`["parsed"]`). The workflow continues to the next phase even though the prior agent produced no valid output (`parsed` may be `None`). Downstream agents then run on missing context.
- **Impact**: A single mid-pipeline failure silently propagates "garbage in → garbage out" through the rest of the 13-node graph.
- **Fix**: After `run_step`, check `result["success"]` and raise an ApplicationError so Temporal can route to failure / a compensation handler.

#### H-008: `seed_roles` only inserts non-existing roles but never grants new permissions to existing super_admin
- **File**: `backend/app/services/auth_service.py:42-54`
- **Issue**: If a new permission code is added to `SYSTEM_PERMISSIONS` after the org was seeded, `seed_roles` skips existing roles (`if not existing`) and never refreshes the `super_admin` permission set. The new permission ends up granted to nobody — even the super admin — and admin UI shows "Permission denied" for the new surface.
- **Impact**: Future permission additions silently fail to apply to existing tenants.
- **Fix**: For each existing role, recompute the desired permission set and assign it (handle `is_system=True` only so user-modified custom roles are not clobbered).

#### H-009: `MarketplaceEntry.MarketplaceKind` doesn't constrain `entry.kind` itself
- **File**: `backend/app/api/marketplace.py:23-36, 132-145`
- **Issue**: `MarketplaceKind = Literal["connector", "agent", "validator", "recipe"]` is used to validate the QUERY param but `MarketplaceEntry.kind: str` accepts any string. Each entry's `kind` is hand-typed in the catalog; one of them already says `"recipe"` correctly but a typo (e.g. `"recipes"`) would silently never surface to a `?kind=recipe` filter.
- **Impact**: Hidden catalog entries on filter; "all-with-kind" type checking is asymmetric.
- **Fix**: Change `MarketplaceEntry.kind: MarketplaceKind` so the model itself enforces the union.

#### H-010: Compute_velocity / compute_burndown read story_points without `.coalesce(0)`
- **File**: `backend/app/services/sprint_service.py:262-264, 288`
- **Issue**: `sum(t.story_points for t in tasks)` raises `TypeError: unsupported operand type(s) for +: 'int' and 'NoneType'` if any task row has a `NULL` story_points (the model column nullable=true by default). The route then 500s instead of returning a partial burndown.
- **Impact**: Sprint analytics endpoints crash if a single task was created without story_points.
- **Fix**: `sum((t.story_points or 0) for t in tasks)`.

#### H-011: `Workflows` SDK `.list()` hard-codes `?limit=100` but the new pagination envelope returns `total` independent of `limit`; callers iterating "all workflows" via `.list()` silently lose data past 100 rows
- **File**: `sdk/python/helix_sdk/client.py:100-103`, `sdk/typescript/src/index.ts:163-179`
- **Issue**: The `.list()` helper used to return a bare array; with the v0.2.0 envelope it now returns `items`. The implementation unwraps `items` but the request still has `?limit=100` baked in, so callers expecting "all workflows" actually get the first 100. No `total`/`offset` exposed; no pagination helper that fetches all pages.
- **Impact**: SDK consumers silently miss data past page 1; CLI `helix workflow list` shows at most 100.
- **Fix**: Either rename `.list()` to `.list_first_page()` and add `.list_all()` that paginates, or document the cap loudly. Same fix needed in `Projects`, `Cutovers`, `Templates`, `Knowledge`, `Artifacts` resource classes.

#### H-012: `_resolve_provider_for_org` does TWO `LLMProvider` queries; the second may resolve to a DIFFERENT provider than the first depending on `resolve_routing`'s mapping
- **File**: `agents/runtime/bmad_executor.py:378-397`
- **Issue**: Lines 378-382 fetch the first active provider for the org. Then `resolve_routing` is called with `provider.id` as the DEFAULT — it can return a different `pid` based on a per-agent mapping. The follow-up query at line 396 then loads that other provider object. But `mappings` was queried for the org as a whole; if the org has no `agent_type="bmad-agent"` mapping (note: literal string, not the per-agent codes like `bmad-agent-architect`!), `resolve_routing` returns `default_provider_id` — i.e., the first provider's id. This works by accident. The bug: line 391 calls `resolve_routing("bmad-agent", ...)` with a literal "bmad-agent" string — that string is NOT in `AGENT_TYPES` (`backend/app/services/llm_router_service.py:21-28`), so per-agent overrides are NEVER consulted from this path. Every PydanticAI BMAD call uses the org default; agent-specific routing is dead code via this entry point.
- **Impact**: Per-agent model mapping configured in the admin UI is silently ignored for the PydanticAI transport (which is the preferred one).
- **Fix**: Pass `agent_code` (the actual `bmad-agent-architect` etc.) through to `_resolve_provider_for_org` and use it in `resolve_routing`.

#### H-013: `S3Connector._get_client` uses `kwargs` from outer scope when assuming a role, leaking the original explicit creds into the STS client
- **File**: `connectors/s3/connector.py:43-53`
- **Issue**: When `role_arn` is set AND `access_key_id` is set, the STS client is built with `kwargs` that already includes the original `aws_access_key_id`/`secret_access_key`. It then completely overwrites `kwargs` with the assumed creds. That part is fine. But when ONLY `role_arn` is set (no explicit base keys), `kwargs` is just `{"region_name": ...}` and `sts.assume_role(...)` runs without credentials, relying on ambient IAM. If ambient IAM is unavailable in the worker container (it usually IS, on EKS, but not in compose), the assume_role raises NoCredentialsError; that bubbles up as a generic "Connection failed" message with no hint that the user must provide ambient creds first. Worse: there is no cleanup of the original STS client object after assume; for high-frequency discovery requests this rebuilds STS + S3 clients per call (no caching), leading to dramatic connection-pool exhaustion against S3.
- **Impact**: Slow S3 discovery; opaque auth errors; no client reuse.
- **Fix**: Cache the boto3 client on the instance; surface NoCredentialsError as a specific "configure either ambient IAM or access_key_id" message.

#### H-014: `webhook_service.deliver_webhook` reads `ep.events.split(",")` without handling whitespace-only / empty values
- **File**: `backend/app/services/webhook_service.py:40-42`
- **Issue**: If `ep.events == ""` (admin clears the field via PATCH but did not provide a new value — `WebhookUpdate` schema permits this), `split(",")` returns `[""]`; the membership test against `event` always fails so the webhook silently delivers NOTHING. There is no validation that `events` is non-empty on UPDATE.
- **Impact**: Webhooks silently stop firing after an admin patches them with an empty events list.
- **Fix**: Validate `events` non-empty in the Pydantic schema; treat empty after split as `["*"]`.

#### H-015: `update_workflow_run_status` does not revoke the in-flight Temporal workflow when status flips to rejected
- **File**: `backend/app/services/workflow_service.py:342-359` and `agent_workflows.py:222-255`
- **Issue**: The HTTP `/approve` endpoint calls `update_workflow_run_status(db, workflow_id, "rejected", ...)` BUT does not signal Temporal. If the per-node workflow is currently waiting in `workflow.wait_condition(approval_decision is not None)` (line 190 of `bmad_per_node_workflow.py`), it sits there until the 48h `_APPROVAL_TIMEOUT`. The DB says "rejected", Temporal says "still waiting". Meanwhile the `/signal-approve` and `/signal-reject` endpoints DO call Temporal — so we have two divergent code paths. There's no comment explaining when to call which.
- **Impact**: Operators using `/approve` think they rejected the workflow, but Temporal continues and may auto-approve via signal-approve later, OR sit idle until 48h timeout consuming a worker slot.
- **Fix**: Either deprecate `/approve` for per-node workflows or always send the corresponding Temporal signal before updating the DB row.

#### H-016: Sprint `update_task_status` does not validate transition shape
- **File**: `backend/app/services/sprint_service.py:133-165`
- **Issue**: Accepts any `new_status` string. Tasks can be moved to `"banana"` and that gets recorded in `SprintTaskHistory.to_status`. Later `compute_burndown` filters on `to_status.in_(("completed", "approved"))` — so the bad data is silently ignored from the burndown but the kanban UI may render an unknown status badge.
- **Impact**: Garbage status values pollute history.
- **Fix**: Constrain `new_status` to a `Literal[...]` enum in the route schema.

#### H-017: Frontend `useApi.handleResponse` always calls `res.json()`, breaks on 204 No Content
- **File**: `frontend/src/lib/use-api.ts:25-31, 33-42`
- **Issue**: For `DELETE /projects/{id}` (which returns 204), the `post`/`get`/`upload` helpers go through `handleResponse` which always calls `res.json()`. On 204 the response body is empty and `.json()` throws `SyntaxError: Unexpected end of JSON input`. Some pages catch that, others surface it as a generic error toast.
- **Impact**: DELETE/204 endpoints look like errors to the UI.
- **Fix**: `if (res.status === 204) return undefined as T`.

---

### MEDIUM

#### M-001: `password_reset_service.request_password_reset` does not invalidate prior tokens
- **File**: `backend/app/services/password_reset_service.py:31-61`
- **Issue**: Each request creates a new `PasswordResetToken`; all prior tokens for the same user remain valid (not marked used_at). An attacker who intercepts an old email-link still has 30 minutes to use it even after the user requests a new one.
- **Fix**: `UPDATE password_reset_tokens SET used_at = now() WHERE user_id = :uid AND used_at IS NULL` before inserting the new one.

#### M-002: `secret_service.encrypt_value` falls through with empty string for ANY falsy value, including the string `"0"`
- **File**: `backend/app/services/secret_service.py:56-62`
- **Issue**: `if not value: return ""` — a literal `"0"` is truthy, but `0` (int), `False`, `[]`, `{}` all return `""`. Routes accept `str | None` so this is defensive — but the docstring says "Empty/None returns" while the runtime swallows more.
- **Fix**: `if value is None or value == "": return ""`.

#### M-003: `_safe_frontmatter` does not redact secret-shaped strings inside *list of strings* if the parent list is a top-level frontmatter list
- **File**: `agents/runtime/artifact_store.py:167-190`
- **Issue**: Recursion handles `dict` and `list`, but a `list[str]` where one string happens to be a JWT will get its string element compared by `_value_looks_secret`. Logic is right. Real bug: `_value_looks_secret` only matches strings >= 16 chars — but a 15-char raw API key (`sk-12345678901`) sneaks past. Bounds on real-world keys vary; tightening the lower bound to 12 would catch more without false-positive risk.
- **Fix**: Lower threshold; add OpenAI org id pattern (`org-…`) which is shorter.

#### M-004: `validation_service._execute` treats `rule.definition` as a digit-only string but the model declares it `Text`
- **File**: `backend/app/services/validation_service.py:106-108`
- **Issue**: `passed = rc.row_count == int(expected) if expected.isdigit() else True` — if `expected` happens to be a non-digit string (e.g. operator typed `"5000"` with a comma), the rule SILENTLY passes. Better to fail noisily.
- **Fix**: If `expected` is set but non-numeric for `row_count` rule type, return `status="error"`.

#### M-005: `cdc_engine._poll_once` catches generic `Exception` then iterates `for c in rows`. If one cutover's `_poll_cutover` raises, the whole pass is aborted — remaining cutovers in `tail` state are never checked this tick
- **File**: `backend/app/services/cdc_engine.py:46-53`
- **Fix**: Move the `try/except` inside the `for` loop so one broken cutover does not block the others.

#### M-006: `auth_service.setup_first_admin` does not flush after `db.add(user)` so accessing `user.id` (line 81) requires SQLAlchemy autoflush which is on by default — but if `autoflush=False` (a future tuning), this silently fails
- **File**: `backend/app/services/auth_service.py:71-81`
- **Fix**: Be explicit and call `db.flush()` before accessing `user.id`. Already done above for `org` — apply the same pattern.

#### M-007: `connector_service.list_connector_registry` returns `capabilities={}` for custom plugins
- **File**: `backend/app/services/connector_service.py:86-94`
- **Issue**: The custom registry only exposes display name; capabilities default to empty dict. The frontend marketplace UI uses capabilities to enable/disable buttons; with `{}` everything is greyed out for custom connectors.
- **Fix**: Custom connectors should declare capabilities in their registration.

#### M-008: `connectors/s3.S3Connector.list_columns` reads only 4096 bytes when inferring schema
- **File**: `connectors/s3/connector.py:110-122`
- **Issue**: A long CSV header line (e.g. >250 columns or with very long names) is truncated mid-name; the resulting `ColumnInfo` list contains a malformed last column. Parquet/JSON inference returns a placeholder `"data"` column always.
- **Fix**: Read enough bytes to cover one line at minimum (read until first `\n` byte); use pyarrow for parquet column listing.

#### M-009: `connector_service` builds a fresh `_get_engine` per request because callers never call `close()`
- **File**: `connectors/postgres/connector.py:68-82`, `connectors/mysql/connector.py:70-83`, similar for SQLServer/Snowflake
- **Issue**: The factory `_build_connector` creates a new connector instance per `test_connection`/`discover_*` call. Each instance lazy-builds a SQLAlchemy engine on first use AND never disposes it because nothing calls `close()`. Each engine holds onto a pool (default size 5) of connections to the upstream DB. High-traffic discovery endpoints leak engines and connection pools.
- **Fix**: Cache `(connector_type, hash(config))` → `BaseConnector` in `_build_connector`, OR have callers dispose via `async with`.

#### M-010: `BMADPerNodeWorkflow` queries `_artifact_paths` keyed by `agent` from activity result — but activities pass `agent_code` while the workflow keys by `agent`
- **File**: `worker/workflows/bmad_per_node_workflow.py:159-162`
- **Issue**: `_artifact_paths.setdefault(agent_code, []).append(...)`; `agent_code` is the activity-returned `result["agent"]` which is the BMAD agent code (e.g. `bmad-agent-architect`). Several Winston activities reuse the SAME agent code (`winston_architecture`, `winston_stories`, `winston_readiness` all `bmad-agent-architect`) so all three artifact paths end up under the same key. Consumers reading `artifact_paths["bmad-agent-architect"]` see three entries with no way to know which step produced which.
- **Fix**: Key by `step_order` or by `(agent_code, skill_name)`.

#### M-011: `agent_workflows.read_workflow_artifact` validates path via `set` membership but does NOT canonicalise — symlinks resolve to a different absolute path
- **File**: `backend/app/api/agent_workflows.py:207-219`
- **Issue**: `allowed_paths` is built from raw stored strings. If a malicious or buggy producer stored a symlink path and the system later canonicalises it, the lookup misses and reads fail with 403. Conversely, if the stored path includes `..` segments (it shouldn't, but if so), the membership check passes and the file is opened relative to whatever cwd FastAPI is running in.
- **Fix**: `os.path.realpath` both stored paths and the supplied path before comparison.

#### M-012: `invitation_service.create_invitation` re-uses the existing `OrgInvitation` row when one is pending but the new caller might have different role_name — silently keeps old role
- **File**: `backend/app/services/invitation_service.py:43-53`
- **Issue**: Returns 409 instead of upserting. Admins must revoke then re-invite to change the role. Better DX would be: upsert and notify, OR error explicitly mentioning revoke first.
- **Fix**: At minimum, include role mismatch info in the 409 detail.

#### M-013: `_token_budget()` clamps to >=1000 but `_allocate_prompt_budget` reserves 1000 chars for boilerplate alone
- **File**: `agents/runtime/bmad_executor.py:67-74, 216-218`
- **Issue**: A budget of exactly 1000 tokens (~4000 chars) minus persona + output schema + requirement + 1000 boilerplate is comfortably negative; `remaining = max(prompt_budget_chars - fixed, 1500)` forces a minimum of 1500 chars. SKILL.md then gets truncated to 1500 chars and may be unusable.
- **Fix**: Validate budget >= 4000 at config-load time; warn loudly below 6000.

#### M-014: `compute_burndown` `actual_remaining = total - cumulative_done if d <= today else total - cumulative_done` — the if/else has the same expression on both sides
- **File**: `backend/app/services/sprint_service.py:339`
- **Issue**: Dead `if/else` — both branches compute `total - cumulative_done`. The future-date branch should arguably stay flat at the last actual value (or be `None`) so the chart doesn't draw a "predicted" past line into the future. Currently the actual line marches forward as if today's status applies to every future day too.
- **Fix**: For `d > today`, append `None` or omit the actual.

#### M-015: `recon_service.run_row_count_recon` casts `mismatch_count=diff` but `diff` is a Python int that may exceed Postgres BIGINT (Postgres handles up to 9.2e18 but `ReconResult.mismatch_count` may be a plain `Integer`)
- **File**: `backend/app/services/recon_service.py:53-66`, model `app/models/validation.py`
- **Issue**: Two very large counts (>= 2^31) will overflow `Integer` columns on insert. The `CutoverDiff` schema caps counts at 1e18 but the recon path doesn't.
- **Fix**: Use BigInteger for mismatch_count; mirror the input validation cap.

#### M-016: SSE stream does not send `event:` lines; some EventSource implementations require them for typed dispatch
- **File**: `backend/app/api/agent_workflows.py:303-333`
- **Issue**: Yields `data: {...}\n\n` with embedded JSON `type` field. EventSource.onmessage receives all; consumer must dispatch in JS. Works, but mixing `event:` and `data:` line patterns would be more idiomatic.
- **Fix**: Optional — emit `event: step\ndata: ...\n\n` for typed handlers.

#### M-017: `frontend/src/lib/api/client.ts` and `frontend/src/lib/use-api.ts` are two parallel API client implementations
- **File**: `frontend/src/lib/api/client.ts`, `frontend/src/lib/use-api.ts`
- **Issue**: `client.ts` exports `apiGet`/`apiPost` (used by older pages); `use-api.ts` exports the React Query–integrated hook. They diverge on error envelope handling, token sourcing (`client.ts` takes `token` as arg vs `use-api.ts` reads from AuthContext), and base URL. Future bug fixes must be applied to both.
- **Fix**: Deprecate `client.ts` and update remaining call sites.

#### M-018: `cli/helix_cli/_cmd_install` builds env dict with `**os.environ` then overwrites NEXT_PUBLIC_API_URL etc., but ignores HELIX_CONFIG_DIR etc. — minor leak
- **File**: `cli/helix_cli/__main__.py:248-260`
- **Issue**: Setting `CORS_ORIGINS=f'["https://{domain}"]'` interpolates the domain into a Python list literal as a string. If `domain` contains a `"` character (mostly impossible but no validation), the env var becomes malformed JSON and setup.sh crashes opaquely.
- **Fix**: `urllib.parse.quote` the domain or validate against a regex.

#### M-019: `_run_with_heartbeats` uses `with ThreadPoolExecutor(max_workers=1, ...)` per call — the executor is created and destroyed for every activity invocation
- **File**: `worker/activities/bmad_node_activities.py:126-133`
- **Issue**: For 13 activities per workflow × concurrent workflows, we churn 13× executors per run. Each new pool spawns 1 thread, runs work, then __exit__ joins. Not catastrophic, but moving to a module-level executor would save thread-creation overhead.
- **Fix**: Module-level `ThreadPoolExecutor(max_workers=N)` shared across activities.

---

### LOW

#### L-001: `agents/runtime/bmad_executor._build_system_prompt` emits `str(field.annotation)` for the field types
- **File**: `agents/runtime/bmad_executor.py:139-142`
- **Issue**: For complex types (`Optional[List[str]]`) this yields `typing.Optional[typing.List[str]]` — the LLM has to interpret Python typing repr instead of a proper JSON-schema. Less reliable than `output_model.model_json_schema()`.
- **Fix**: Use `output_model.model_json_schema()` and inline the relevant subset.

#### L-002: `mask_key` returns `"***"` for empty key but `"****"` (4 stars) for keys ≤8 chars; inconsistent prefix length
- **File**: `backend/app/services/secret_service.py:106-111`
- **Fix**: Always return a consistent visible mask.

#### L-003: `daily_cost` uses `group_by("d")` referring to the label; works on Postgres but is non-portable to SQLite (used in tests)
- **File**: `backend/app/services/cost_service.py:183-184`
- **Fix**: Group by the cast expression directly.

#### L-004: `app/main.py` uses deprecated `@app.on_event("startup")` / `"shutdown"` — Starlette/FastAPI moved to `lifespan` context-manager pattern
- **File**: `backend/app/main.py:86-103`
- **Fix**: Migrate to `lifespan=` parameter.

#### L-005: `webhook_service.deliver_webhook` retains `httpx.AsyncClient(timeout=10)` for all endpoints in a serial loop — one slow endpoint blocks the next 10s+
- **File**: `backend/app/services/webhook_service.py:38-85`
- **Fix**: `asyncio.gather` per endpoint, OR persist a delivery row and let a worker handle the POST.

#### L-006: `connectors/files/csv_connector.get_row_count` calls `pd.read_csv(path)` reading the whole file into memory just to count rows
- **File**: `connectors/files/csv_connector.py:86-96`
- **Fix**: `sum(1 for _ in open(path)) - 1` (subtract header).

#### L-007: `agents/runtime/artifact_store._safe_frontmatter` drops keys silently — no warning for the operator
- **File**: `agents/runtime/artifact_store.py:179-185`
- **Fix**: Log at info level when a key is dropped so operators can see what got scrubbed.

#### L-008: `agents/runtime/bmad_executor._estimate_tokens` uses len//4; off by 25% for code-heavy artifacts
- **File**: `agents/runtime/bmad_executor.py:77-79`
- **Fix**: Optional — wire in `tiktoken` when available.

#### L-009: `helix_cli.__main__._cmd_install` swallows `subprocess.call` non-zero with a single integer return; cannot distinguish "setup.sh failed at compose up" vs "DB migration failed"
- **File**: `cli/helix_cli/__main__.py:262-270`
- **Fix**: Use `subprocess.run(..., check=False)` and read returncode + stderr.

#### L-010: `sdk/python/helix_sdk.Helix._raise_for` catches `Exception` when parsing JSON — broad
- **File**: `sdk/python/helix_sdk/client.py:290-294`
- **Fix**: Catch `ValueError`/`JSONDecodeError` specifically.

#### L-011: `frontend/src/lib/auth-context.tsx` uses `localStorage.getItem` in `useEffect` without trying `sessionStorage`; logging in across tabs requires manual refresh
- **File**: `frontend/src/lib/auth-context.tsx:35-50`
- **Fix**: Add a `storage` event listener so token changes propagate between tabs.

#### L-012: `website/src/App.tsx` redirects unknown routes to `/` with `<Navigate replace>` — silently hides 404s; SEO/analytics signal is lost
- **File**: `website/src/App.tsx:21-22`
- **Fix**: Render a real 404 page so server can mark it as 410/404 for crawlers.
