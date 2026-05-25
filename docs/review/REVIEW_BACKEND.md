# Backend Code Review

> Generated 2026-05-26. Scope: `backend/` + `connectors/` (top-level connector adapter package). Reviewer: Claude Opus 4.7. Every file under `backend/app/`, `backend/alembic/versions/`, `backend/tests/`, `backend/Dockerfile`, `backend/requirements*.txt`, plus the standalone `connectors/` package was read in full.

---

## 1. High-level architecture

### Layers
- **`app/main.py`** — FastAPI entrypoint. Mounts 18 routers under `/api/v1`, configures CORS, request-id middleware, GZip, Prometheus, OpenTelemetry, body-size enforcement, SlowAPI.
- **`app/api/*`** — 18 routers. One per resource (auth, projects, sprints, llm_providers, connectors, artifacts, code_reviews, agent_workflows, validation, audit, system, encryption, invitations, webhooks, usage, superadmin, users, health). Routers are thin — they resolve `org_id`, delegate to a service, optionally `write_audit`.
- **`app/services/*`** — 18 service modules. Hold the business logic (CRUD, encryption, BMAD bridging, recon, validation, webhook delivery, email rendering, sprint seed, etc.). The router-to-service boundary is mostly clean, but a couple of routers still inline `db.query()` (e.g. `projects.py` archive/restore/delete; `superadmin.py`).
- **`app/models/*`** — 10 SQLAlchemy ORM modules: `identity`, `project`, `agents`, `artifacts`, `llm`, `validation`, `observability`, `workflow`, `webhook`, `encryption`, `sprint`. `BaseModel` provides `id` (UUID4 String(36)), `created_at`, `updated_at`.
- **`app/schemas/*`** — 6 Pydantic v2 modules (`identity`, `project`, `agents`, `artifacts`, `llm`, `sprint`). All response models use `model_config = {"from_attributes": True}`.
- **`app/auth/`** — `jwt.py` (token issue/decode/revoke via Redis hash) + `dependencies.py` (RBAC + org-resolution helpers).
- **`app/core/`** — `config.py` (Pydantic `Settings`), `logging_config.py` (JSON logs + `RequestIdMiddleware`), `redis_client.py` (single shared client w/ silent fallback).
- **`app/db/`** — `session.py` ships both sync and async engines.
- **`app/storage/local.py`** — local-FS artifact writer with path-traversal hardening.
- **`app/rate_limiting.py`** — single shared SlowAPI `Limiter` (enabled only in `APP_ENV == "production"`).

### Request flow
```
client → main.py middleware stack
        (RequestIdMiddleware → body-size guard → CORS → GZip)
      → SlowAPI limiter (production only)
      → router (api/*.py)
      → auth dep (get_current_user_id) decodes JWT, checks revocation
      → org-scope dep (resolve_active_org_id / get_current_organization_id)
      → permission dep (require_permission / require_role) if admin route
      → service (services/*.py) — does the work, returns ORM/Pydantic
      → write_audit() persisted with HMAC chain hash
      → response (Pydantic from_attributes)
```

### Cross-cutting concerns
- **Audit chain** — `app/api/audit.py::write_audit` writes one `audit_logs` row per mutation, computing an HMAC-SHA256 of (id, org, actor, action, entity_type, entity_id, prev_hash) keyed by `JWT_SECRET_KEY`. `/audit-logs/verify` walks the chain to detect tampering. CSV + PDF exporters are available.
- **Rate limiting** — SlowAPI keyed by remote address; disabled outside production. Applied to auth, invitations, connector tests, discovery, and impersonation.
- **Encryption** — two distinct paths coexist: (a) `services/secret_service.py` Fernet-derives a key from `ENCRYPTION_KEY` (deterministic SHA256→base64) and is used for LLM secrets + connection configs + webhook signing secrets; (b) `services/envelope_encryption_service.py` implements per-org DEKs (KEK encrypts org DEK in `org_data_encryption_keys`). The codebase ships both but only path (a) is actually used by callers — path (b) is exposed via `POST /admin/org/rotate-dek` only.
- **Observability** — Sentry, Prometheus FastAPI instrumentator, OpenTelemetry (FastAPI + SQLAlchemy), JSON structured logging in prod with `X-Request-ID` propagation.
- **Tenancy** — every model that holds tenant data has `organization_id` and the matching ORM query filters by it. Org resolution flows through `resolve_active_org_id` / `get_current_organization_id` which both gate on `OrganizationMember.status == "active"`.
- **Validation / recon** — minimal: row-count + schema-compare. Validation runs are kicked off via `BackgroundTasks`.

---

## 2. File-by-file review

### backend/app/main.py
**Purpose:** FastAPI app factory. Wires middleware, routers, and observability.
**Reviewed lines:** 130.

#### Issues
- 🟠 **HIGH** lines 80-87: CORS is configured with `allow_credentials=True` *and* `allow_origins=settings.CORS_ORIGINS` *and* `allow_origin_regex=settings.CORS_ORIGIN_REGEX or None`. In production the regex is forced empty (`config.py` validates this), but in dev the default regex `^https?://(localhost|127\.0\.0\.1)(:\d+)?$` is paired with `allow_credentials=True`. The dev-only path is acceptable, but make the production guard for `allow_credentials=True` explicit (CORS + credentials + permissive regex is the classic exfil pattern).
- 🟡 **MED** lines 67-77: `enforce_body_size` only checks `Content-Length`. Clients that stream without a `Content-Length` header (`Transfer-Encoding: chunked`) bypass the cap entirely; the upload path in `api/artifacts.py` then `await file.read()` into memory. Add a streaming guard (track bytes read inside `await call_next`).
- 🟡 **MED** lines 30-31: `configure_logging(settings.APP_ENV)` runs at import time before any test fixture patches the env. That makes pytest verbose-mode logging brittle.
- 🔵 **LOW** lines 32-56: heavy module-level imports of `sentry_sdk` + `opentelemetry.*` happen at app boot whenever `SENTRY_DSN` / `OTEL_ENDPOINT` are set. Fine, but make sure these env vars are unset in CI to keep import cost low.
- 🔵 **LOW** line 66: `# type: ignore[arg-type]` suggests SlowAPI's `_rate_limit_exceeded_handler` is typed loosely. Consider wrapping in a thin adapter to keep the type ignore localised.

#### Improvements
- Pull middleware ordering into a comment block. Currently the order RequestId → body-size → CORS → GZip is correct (RequestId outermost so logs always have the id) but easy to break with future additions.
- Move the Sentry/OTel init into a `setup_observability(app)` helper for testability.

---

### backend/app/rate_limiting.py
**Purpose:** Single shared SlowAPI limiter instance.
**Reviewed lines:** 11.

#### Issues
- 🟠 **HIGH** line 10: limiter is **disabled outside production** (`enabled=settings.APP_ENV == "production"`). That means every limiter-decorated test passes regardless of intended caps and rate-limit bugs (eg. missing handler integration) ship to prod silently. Add a separate flag (`RATE_LIMIT_ENABLED`) defaulting to `True` and override only in test fixtures.
- 🟡 **MED** line 9: `key_func=get_remote_address` keys by client IP, which is the proxy IP behind any deployment with a load balancer / CDN. Either trust `X-Forwarded-For` (after validating `TRUSTED_PROXIES`) or fall back to a user-scoped key once authenticated. Today an attacker behind a corporate NAT trivially DoSes legitimate users.

---

### backend/app/core/config.py
**Purpose:** Pydantic `Settings` (env-driven config).
**Reviewed lines:** 93.

#### Issues
- 🔴 **CRITICAL** lines 16, 28, 30: `APP_SECRET_KEY`, `JWT_SECRET_KEY`, `ENCRYPTION_KEY` all default to `"change_me"` / `"change_me_32_byte_key"`. The `model_post_init` guard in lines 60-90 only runs in `APP_ENV == "production"`. A developer running `docker-compose up` with the canonical defaults gets a JWT secret of `"change_me"`, which is the same value across every fork. Anyone with the source can forge tokens against any non-production deployment. Force a random-default via `Field(default_factory=lambda: secrets.token_hex(32))` and *fail closed* if the default ever ships.
- 🟠 **HIGH** line 21: `DATABASE_URL` default hard-codes the username + password `helix:helix_password`. This bleeds into docs and tests as the canonical value. Use a dummy value that obviously fails.
- 🟠 **HIGH** lines 32-33: `CORS_ORIGINS` defaults to `["http://localhost:3000", "http://localhost:8080"]` AND `CORS_ORIGIN_REGEX` defaults to `r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"`. Combined with `allow_credentials=True` in `main.py`, **any HTTP page on localhost** can ride a logged-in dev's cookies. Acceptable for dev only if developers always treat localhost as adversarial; many don't.
- 🟡 **MED** line 11: `"extra": "ignore"` swallows typos in env var names. Set `extra="forbid"` and explicitly accept the Postgres/Temporal vars you want to share.
- 🟡 **MED** line 56: `EMAIL_FROM_NAME: str = "Helix Migration"` is hard-coded; if anyone customises, the rendered subject lines (`[{settings.APP_NAME}] …`) still say "Helix Migration" because they read `APP_NAME` rather than `EMAIL_FROM_NAME`. Minor inconsistency.
- 🔵 **LOW** lines 82-90: the base64 validation for `ENCRYPTION_KEY` adds `+ "=="` padding before decoding. This silently accepts inputs whose padding is wrong but length-after-padding fits — a *technically* invalid key may pass. Use `base64.urlsafe_b64decode` with strict padding by computing `key + "=" * (-len(key) % 4)`.

#### Improvements
- Add a `validate_assignment=True` so runtime config mutation also re-validates.
- Add `model_config["env_prefix"]` (e.g. `HELIX_`) to disambiguate vs Postgres/Temporal env vars instead of `extra="ignore"`.

---

### backend/app/core/logging_config.py
**Purpose:** JSON + plain-text logging setup; `X-Request-ID` propagation middleware.
**Reviewed lines:** 35.

#### Issues
- 🟡 **MED** lines 32-34: the request id is stored on `request.state` and echoed in the response header but **never injected into log records**. The class docstring says "propagate to log context" but no `logging.Filter` / `LogRecord` field is added. As a result a log entry created in a request handler has no `request_id` field — the correlation promise is unfulfilled.
- 🔵 **LOW** line 24: `logging.getLogger("uvicorn.access").setLevel(logging.WARNING)` silences access logs. That's a deliberate choice for prod (Prometheus replaces them) but it bites local dev when debugging — surface it in README.

#### Improvements
- Add a `contextvars.ContextVar("request_id")` set inside `dispatch` and a `logging.Filter` that copies it onto every emitted record.

---

### backend/app/core/redis_client.py
**Purpose:** Lazy-init shared Redis client; silent fallback to `None`.
**Reviewed lines:** 23.

#### Issues
- 🟠 **HIGH** lines 16-22: `get_redis()` caches `None` permanently after the first failure. If Redis comes up *after* the API process started, token revocation stays disabled forever until restart. Cache the connect attempt with a short cooldown.
- 🟡 **MED** line 18: `decode_responses=True` is correct but no `health_check_interval` — long-lived idle connections may time out. Add `health_check_interval=30` or `socket_keepalive=True`.
- 🟡 **MED** lines 20-21: a Redis outage degrades to silent "token revocation disabled". In a strict security posture that's the wrong default. Make it a config knob (`STRICT_REVOCATION_REQUIRED=true` rejects requests until Redis is reachable).

---

### backend/app/auth/jwt.py
**Purpose:** Password hashing, JWT issue/decode/revoke.
**Reviewed lines:** 71.

#### Issues
- 🟠 **HIGH** line 34: `revoke_token` defaults TTL to `settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60` *at import time*. If a custom token was issued with a non-default TTL (e.g. the 15-minute impersonation token in `superadmin.py`), revocation TTL is still the default — the revocation entry could expire before the token, allowing a "revoked" token to be re-accepted. Compute TTL from the actual `exp` claim.
- 🟠 **HIGH** lines 56-63: `decode_access_token` does not enforce the algorithm allowlist via `jwt.decode(... algorithms=["HS256"], options={"require": ["exp", "sub"]})` and doesn't pass `audience` / `issuer` — token confusion attacks (alg=none, alg switch) are not impossible with python-jose's history. Pin algorithms explicitly *and* require `exp` + `sub`.
- 🟡 **MED** lines 38-42: `revoke_token`'s exception swallow logs nothing; a Redis failure during logout means the user is silently still logged in. At minimum `logger.warning("Token revocation failed: %s", exc)`.
- 🟡 **MED** line 30: JWT payload has only `{sub, exp}`. No `iat`, `jti`, `org_id`. Adding `iat` enables future password-change-invalidates-old-tokens semantics; adding `jti` enables single-use refresh.
- 🔵 **LOW** line 17: `hashlib.sha256(token.encode()).hexdigest()` is fine but the Redis key includes the prefix in cleartext — that's intentional (debuggability), just confirm in code review.

#### Improvements
- Use the `passlib` package consistently (it's already in `requirements.txt`) — currently the code imports `bcrypt` directly while `passlib[bcrypt]` is a declared dependency. Pick one.
- Move JWT settings into a `JWTConfig` dataclass so audience/issuer/algorithms are co-located.

---

### backend/app/auth/dependencies.py
**Purpose:** Reusable FastAPI deps for user lookup, org resolution, permission checks.
**Reviewed lines:** 115.

#### Issues
- 🟡 **MED** lines 19-30: `_active_membership` uses `db.query(...).first()` with no ordering — if a user is in multiple orgs, the choice of "current org" is non-deterministic. The system effectively assumes one active membership per user but does not enforce that uniqueness at the DB level. Add a partial unique index `WHERE status='active'` on (`user_id`) or an explicit "current_org" pointer on `User`.
- 🟡 **MED** lines 33-37 + 40-48: there are two functions that do the same thing — `get_current_organization_id` (dependency form) and `resolve_active_org_id` (helper form). They share `_active_membership` but their return types differ (`str` vs `str(membership.organization_id)`). Consolidate to one shape (cast to `str` consistently).
- 🟡 **MED** lines 89-98: `require_permission` returns the **user_id**, not a "permission verified" sentinel. Callers `Depends(require_permission(...))` and bind to `user_id` — works, but the indirection is non-obvious. Document that this dep also functions as a `user_id` resolver.
- 🔵 **LOW** line 71: `if user.is_super_admin: return True` bypasses the org-membership check. Correct for platform-admin endpoints, but a super-admin who has *no* active membership can still mutate any org's data when they ride a path that uses both `require_permission` and `resolve_active_org_id`. Confirm whether that's intentional.

#### Improvements
- Cache `_active_membership` per-request via FastAPI dependency caching (or `functools.lru_cache` on `user_id`) — it's called on virtually every authenticated request.

---

### backend/app/storage/local.py
**Purpose:** Path-traversal-safe local artifact writer.
**Reviewed lines:** 76.

#### Issues
- 🟡 **MED** line 9: `MAX_UPLOAD_BYTES = settings.MAX_UPLOAD_MB * 1024 * 1024` is computed at import time. Tests / hot-reload that change `MAX_UPLOAD_MB` don't see the new value.
- 🟡 **MED** line 8: `ALLOWED_TYPES = {"py", "sql"}` — file type allowlist is hard-coded. The product roadmap covers SAS / PL/SQL / ABAP migrations; this will need extension. Move to config.
- 🔵 **LOW** lines 30-35: `_assert_inside_storage_root` uses `Path.resolve()` which dereferences symlinks. On Windows the resolved path's drive letter case may not match `storage_root` (compared by `Path.relative_to`) and raise. Add a small unit test against a path with mixed case on Windows.

#### Improvements
- Strong: this module is otherwise solid. The two-pass sanitization (`Path.name` twice with `\\`→`/` swap) covers Windows-on-Linux corner cases nicely.

---

### backend/app/models/base.py
**Purpose:** Abstract `BaseModel` with `id`, `created_at`, `updated_at`.
**Reviewed lines:** 14.

#### Issues
- 🟡 **MED** line 12: `id = Column(String(36), …)` everywhere. Identity tables in the first migration (`25b337c73f7a_identity_tables.py`) use `postgresql.UUID(as_uuid=True)`, but every other table uses `String(36)`. This mismatch means JOINs between `users.id` (UUID) and `organization_members.user_id` (also UUID in that migration) work, but JOINs across newer mixed tables (e.g. `audit_logs.actor_id` String → `users.id` UUID) rely on Postgres's implicit text/UUID coercion, which (a) silently breaks indices and (b) is dialect-specific.
- 🔵 **LOW** line 13-14: `server_default=func.now()` is correct; `onupdate=func.now()` only fires for ORM-driven updates, not raw `UPDATE` statements.

#### Improvements
- Move toward a uniform `id` strategy. Either all UUID (with proper Postgres `gen_random_uuid()` server default) or all `String(36)` and update the identity migration.

---

### backend/app/models/__init__.py
**Purpose:** Aggregate model imports so Alembic + tests pick them all up.
**Reviewed lines:** 14.

No findings beyond: keep alphabetical-by-module to make conflict resolution painless.

---

### backend/app/models/identity.py
**Purpose:** Users, organizations, roles, permissions, memberships, password-reset tokens, invitations.
**Reviewed lines:** 92.

#### Issues
- 🟠 **HIGH** line 38: `Role.name` is **not unique per org**. Two `super_admin` roles can be created for the same `organization_id`. The `seed_roles` helper guards with a query, but a concurrent first-admin setup race could double-insert. Add `UniqueConstraint("organization_id", "name")`.
- 🟠 **HIGH** lines 73-80: `OrgInvitation` is declared in models but neither `expires_at`, `accepted_at`, nor `status` columns are present on the model — yet `services/invitation_service.py` writes `invite.expires_at = …`, `invite.status = …`, `invite.accepted_at = …`. The migration `e6f7a8b9c0d1_invitations_table.py` does define those columns, but the ORM model is incomplete and will fail to load them via `Pydantic.from_attributes` for any field that exists in DB but not in the model. The endpoint `GET /invitations` references `i.status / i.expires_at / i.accepted_at` and only works because SQLAlchemy reflectively sees the columns due to `__tablename__`. Add the missing `Column(...)` declarations explicitly.
- 🟡 **MED** lines 86-89: `OrganizationMember` has no `UniqueConstraint("user_id", "organization_id")` — a user can have multiple memberships in the same org. Combined with the "non-deterministic first()" in `_active_membership`, this is a footgun.
- 🟡 **MED** line 29: `preferences = Column(JSON, nullable=True)` — `users.preferences` is a free-form JSON blob with a 16 KiB ceiling enforced at the API layer (`api/users.py`). Add a CHECK constraint at the DB level so direct DB writes can't blow past the limit.
- 🔵 **LOW** line 67: `password_reset_tokens.user_id` is `String(36)` but the migration uses `UUID(as_uuid=False)`. Both serialize the same on the wire, but the type mismatch between model and migration is a latent footgun.

---

### backend/app/models/project.py
**Purpose:** Project, SubProject, MigrationRequirement, SourceConnection, TargetConnection, Schema/Table/Column metadata.
**Reviewed lines:** 114.

#### Issues
- 🟡 **MED** line 16: `owner_id = Column(String(36), nullable=False)` — no foreign key to `users.id`. Orphaned owner_ids cannot be detected by referential integrity.
- 🟡 **MED** lines 47-78: `SourceConnection.organization_id` and `TargetConnection.organization_id` are `String(36)` with no `ForeignKey("organizations.id")`. They store the org id redundantly (also reachable via `project.organization_id`) — that's good for query efficiency, but enforce the FK so a project move (currently impossible but plausible) doesn't strand connections.
- 🟡 **MED** line 53/71: `connector_type = Column(String(50))` is a free-text column — there's no enum constraint. A typo (`postgresss`) is accepted by the API and silently fails later in `_build_connector`.
- 🔵 **LOW** line 87: `schema_type = Column(String(20), default="source")` — same enum-as-string concern.

---

### backend/app/models/agents.py
**Purpose:** AgentDefinition / AgentTask / AgentOutput / PromptTemplate / PromptVersion.
**Reviewed lines:** 65.

#### Issues
- 🟠 **HIGH** lines 27-29: `token_usage`, `started_at`, `finished_at` are all `String(50)`. `started_at` / `finished_at` should be `DateTime(timezone=True)`; `token_usage` should be `Integer` (or `JSONB` if multi-field). The migration `a1b2c3d4e5f6_proper_column_types.py` migrated several other tables off-string but missed these. Plan a follow-up migration.
- 🟡 **MED** line 19: `project_id` is `String(36)` with no FK constraint — orphan tasks survive a project delete.
- 🟡 **MED** line 35-38: `AgentOutput.task_id` has a FK but no `ON DELETE` clause — orphan cleanup falls on the relationship's `cascade="all, delete-orphan"` which is ORM-only (a raw SQL `DELETE FROM agent_tasks` will fail).

---

### backend/app/models/artifacts.py
**Purpose:** Code artifact storage, version history, lineage, review, approval.
**Reviewed lines:** 78.

#### Issues
- 🟠 **HIGH** line 27: `version_number = Column(String(20), nullable=False)` — sorting by `version_number DESC` (`artifact_version_service.list_versions` line 65; `code_reviews.py` line 60) gives lexicographic order. `"10"` sorts before `"2"`. Either use Integer or zero-pad / SemVer-parse.
- 🟠 **HIGH** lines 36, 79: `approved_at = Column(String(50))` should be `DateTime(timezone=True)`. Same H-6 leftover as agents.py.
- 🟡 **MED** line 28: `content_hash = Column(String(64))` but no unique constraint on `(artifact_id, version_number)`. Two versions with the same number are allowed.
- 🔵 **LOW** line 18-21: cascade rules differ per relationship — `versions`, `dependencies`, `lineage` use `cascade="all, delete-orphan"` but `ArtifactReview` and `ArtifactApproval` have no back-ref and are never cascaded. Deleting a `CodeArtifactVersion` orphans its reviews/approvals.

---

### backend/app/models/llm.py
**Purpose:** LLM providers, secrets, agent→provider mappings.
**Reviewed lines:** 47.

#### Issues
- 🟡 **MED** line 32: `rotated_at = Column(String(50))` — should be `DateTime(timezone=True)`. Worse, `services/llm_provider_service.py::rotate_key` writes `rotated_at=str(uuid.uuid4())` (line 91) — a UUID into a "rotated_at" timestamp column! Clearly a bug/leftover from a copy-paste; rotation timestamps are unreadable.
- 🟡 **MED** lines 37-47: `LLMAgentMapping` has no unique constraint on `(organization_id, agent_type)`. Two mappings for the same (org, agent) will both be returned by `list_agent_mappings`, and `resolve_routing` returns the first one. The "replace" path covers it, but direct `create_agent_mapping` calls don't.
- 🔵 **LOW** line 30: `encrypted_api_key = Column(String(500))` — Fernet output is base64 and can exceed 500 chars for long keys with associated data. 500 happens to be enough for current keys but is risky long-term; consider `Text`.

---

### backend/app/models/validation.py
**Purpose:** Validation rules, runs, results; reconciliation runs + results.
**Reviewed lines:** 47.

#### Issues
- 🟡 **MED** lines 7-11: `project_id` is `String(36)` with no FK constraint. Validation rules survive project deletion.
- 🟡 **MED** lines 27-28: `observed_value` / `expected_value` are `String(255)`. The validation service line 117 truncates if longer, but losing data here makes debugging mismatches hard. Use `Text`.
- 🔵 **LOW** line 36: `recon_runs.status` has no enum constraint.

---

### backend/app/models/observability.py
**Purpose:** AuditLog + SystemHealthCheck.
**Reviewed lines:** 22.

#### Issues
- 🟠 **HIGH** line 12: `event_metadata = Column("metadata", Text, nullable=True)` — the column is renamed in DB to `metadata` (reserved word collision avoidance with SQLAlchemy's `Base.metadata`). Future migrations that touch the table must use the DB name. Add a comment to clarify.
- 🟡 **MED** line 9: `actor_id` is nullable but has no FK to `users.id`. Audit log retains actor id forever even after user deletion — that's *correct* for audit retention. Keep it nullable + leave the FK off explicitly.
- 🟡 **MED** line 15: `entry_hash = Column(String(64), nullable=True)`. Nullable is wrong — every row should have a hash. Set `nullable=False` once backfill is complete (an Alembic data migration).

---

### backend/app/models/workflow.py
**Purpose:** Workflow runs + steps (BMAD pipeline persistence).
**Reviewed lines:** 44.

#### Issues
- 🟡 **MED** lines 16-19: `organization_id`, `project_id`, `requirement_id` are `String(36)` with no FKs. Org delete leaves workflows orphaned.
- 🔵 **LOW** line 36: `parsed_output_json = Column(JSONB, …)` — this is Postgres-specific. Tests that use SQLite would fail; thankfully `conftest.py` uses Postgres for tests so it's fine, but flag it.

---

### backend/app/models/webhook.py
**Purpose:** WebhookEndpoint + WebhookDelivery.
**Reviewed lines:** 25.

#### Issues
- 🟡 **MED** lines 11-12: `events = Column(Text, nullable=False, default="*")` — events list is comma-separated text. `webhook_service.py::deliver_webhook` splits on `,`. An event name containing a comma would break this; use a normalised join table or `JSONB`.
- 🟡 **MED** line 19: `endpoint_id` has no FK constraint. Deliveries survive endpoint deletion (might be intentional for audit, but make it explicit).

---

### backend/app/models/encryption.py
**Purpose:** Per-org Data Encryption Keys (envelope encryption).
**Reviewed lines:** 14.

#### Issues
- 🟡 **MED** line 11: `key_version = Column(String(50), default="1")` — version is a string, but `rotate_dek` increments via `int(old.key_version) + 1`. Use Integer.
- 🔵 **LOW** line 10: `encrypted_dek = Column(String(512))` — Fernet output of a 32-byte key fits comfortably; safe.

---

### backend/app/models/sprint.py
**Purpose:** Sprint Management — sprints, tasks, risks, approvals, releases, mapping graph, agent executions, task history.
**Reviewed lines:** 188.

#### Issues
- 🟡 **MED** lines 28-44: `Sprint.status` and `Sprint.health` use `String(40)` with inline comments listing allowed values. Add CHECK constraints or use proper enums; today the API trusts upstream not to send `status="totally-broken"`.
- 🟡 **MED** line 33: `Sprint.index` is an Integer but has no unique-per-project constraint. Two sprints can share `index=1` and the active sprint resolver returns the first by `ORDER BY index ASC`.
- 🟡 **MED** lines 50-72: `SprintTask` fields are wide and untyped — `priority="P3"`, `risk_level="low"`, `validation_status` are all free-string. Same enum-as-string smell. Note that `SprintTask.actual_hours` is nullable Integer; `services/sprint_service.py::create_task` writes `actual_hours=data.actual_hours`, OK.
- 🟡 **MED** lines 70-71: `dependency_ids` and `artifact_ids` are `Column(JSON)` lists. No DB-level validation that they reference real rows.
- 🔵 **LOW** lines 127-144: `MappingNode.position_x / position_y` default to `0` — first canvas render piles every node on the origin until manually positioned. Seed sets them; user-created nodes won't have coordinates.

---

### backend/app/db/session.py
**Purpose:** SQLAlchemy sync + async engine and session factories.
**Reviewed lines:** 32.

#### Issues
- 🟠 **HIGH** line 13: `_async_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)` — the replacement only handles the bare prefix. If a user supplies a fully qualified `postgresql+psycopg2://…`, the async engine ends up with `postgresql+psycopg2://…` rebound to `postgresql+asyncpg…` only if the substring matches, which it doesn't. The async engine will then try to load psycopg2 as the async dialect → ImportError at first async call. Document the supported URL shape or do a proper regex split.
- 🟡 **MED** lines 7, 14: pool sizes (`10` + `max_overflow=20`) are hard-coded. Should come from config.
- 🟡 **MED** lines 22-27: `get_db` is a sync generator. Routes mixing async + sync sessions create thread-pool pressure. Most routes are sync (correctly) but `agent_workflows.py`'s async routes still call `Depends(get_db)` which gives them a sync session blocked in the loop's executor.
- 🔵 **LOW**: no `engine.dispose()` hook on app shutdown — uvicorn shutdown leaves dangling connections in dev hot-reload.

---

### backend/app/api/health.py
**Purpose:** Public liveness probe.
**Reviewed lines:** 12.

No findings — minimal and correct. Consider adding a separate `/api/v1/ready` that checks DB + Redis before returning 200 (system/health already does this but it's auth-gated; readiness probes need an unauthenticated endpoint).

---

### backend/app/api/auth.py
**Purpose:** First-admin setup, login, logout, refresh, password reset.
**Reviewed lines:** 84.

#### Issues
- 🟠 **HIGH** line 37: `setup_first_admin` returns HTTP 200 (FastAPI default) but the OpenAPI spec implies 201 for creation. Minor REST hygiene.
- 🟠 **HIGH** lines 35-36: `org_id = user.memberships[0].organization_id` — if `memberships` is empty (race condition during setup), this raises `IndexError → 500`. Always reachable in tests when `setup_first_admin` itself failed partway.
- 🟡 **MED** line 30: `@limiter.limit("5/minute")` — but limiter is disabled in dev (see rate_limiting.py finding). The `first-admin` endpoint should additionally check "first admin already exists" inside the limit so attackers can't waste the limit window after the system is set up.
- 🟡 **MED** line 53: `user_logout` accepts `credentials` then revokes — but never validates that the token in the header matches the user_id from `get_current_user_id`. They will because both deps read the same header, but the redundancy + lack of comment invites future regression.
- 🟡 **MED** lines 67-76: password-reset flow leaks timing — the call always returns 202 but only schedules a background send if the user exists. An attacker timing the 202 response can probabilistically distinguish valid emails. Mitigate by always scheduling a `send_email` (even to a noreply sink) or by adding random delay.
- 🔵 **LOW** line 75: `BackgroundTasks.add_task(send_email, …)` — exceptions in the task vanish; logs only. That's a documented FastAPI limitation, but operators should be aware.

#### Improvements
- Move `_assert_first_admin_not_present` upfront in `setup_first_admin` to fail before any encryption key is touched.

---

### backend/app/api/llm_providers.py
**Purpose:** CRUD + catalogue + test connection for LLM providers; agent→provider mappings.
**Reviewed lines:** 136.

#### Issues
- 🟠 **HIGH** lines 28-30: `_org(db, uid)` does a fresh `get_current_user(db, uid).memberships[0].organization_id`. (a) duplicates `_active_membership` logic; (b) doesn't filter by `status == "active"`; (c) IndexError on no memberships. Reuse `resolve_active_org_id`.
- 🟡 **MED** line 75: `api_create_provider` declares `request: Request = None` (default None!) — if FastAPI ever bypasses the dependency, audit logging crashes. Convert to required `request: Request`.
- 🟡 **MED** lines 88-92: `api_update_provider` calls `_org(db, user_id)` *twice* (once into `org_id`, again in `write_audit`). Tiny inefficiency that's repeated across this file.
- 🟡 **MED** lines 103-107: `api_test_provider` is rate-limited per IP — but a test against a misconfigured provider can hang for `provider.timeout` seconds (default 60). 10/min × 60s = a single attacker can monopolise the test pool. Lower the cap, or short-circuit the test on prior failure.
- 🔵 **LOW** lines 24-25: top-of-file imports from `agents.runtime` are positioned mid-module under a heredoc-style comment. Move them to the top with the rest of the imports.

#### Improvements
- Audit calls share the same shape; extract `_audit("llm_provider_xxx", entity_id, request)` to a one-liner inside this router.

---

### backend/app/api/projects.py
**Purpose:** Project CRUD + subproject/requirement nested resources + connection CRUD + discovery endpoints.
**Reviewed lines:** 259.

#### Issues
- 🟠 **HIGH** lines 67-90: archive/restore/delete each do `db.query(Project).filter(Project.id == project_id).first()` after `ensure_project_access`. The query is redundant — `ensure_project_access` already returns the row — and the second query has **no `organization_id` filter** (it filters on `id` only). Cross-tenant safety relies entirely on `ensure_project_access` being called first; an accidental refactor could remove it and you'd silently leak archive/restore to other tenants. Reuse the row returned by `ensure_project_access`.
- 🟠 **HIGH** lines 161-169: `api_test_source` (and target / discover endpoints) call `get_source_config` which loads + decrypts credentials. The endpoint persists `conn.status = "active"` based on the live test — that's a write performed *inside a `@limiter.limit`-decorated async route* with **no `db.commit` error handling**. A failed commit silently leaves the status unchanged. Wrap in try/except + log.
- 🟡 **MED** line 35-36: `_org_id` duplicates `_active_membership` (third copy in the codebase). Pulled into `resolve_active_org_id`; just import and use it.
- 🟡 **MED** lines 49-58: `api_list_projects` paginates *after* fetching all rows (`rows[offset : offset + limit]`). For an org with 10k+ projects that loads them all into memory. Push the slice down into `list_projects` (and the service into the query).
- 🟡 **MED** lines 246-258: `add_schema`, `add_table`, `add_column` lack audit logging. Inconsistent with the rest of the router.
- 🔵 **LOW** multiple lines: `from app.api.audit import write_audit` is repeated inside function bodies. Hoist to top-of-file.
- 🔵 **LOW** lines 95-105: `api_delete_project` performs a *soft delete* (status="deleted") but uses HTTP 204 — by REST convention 204 implies "removed entirely". OK for tombstoned soft-delete, but worth a comment.

#### Improvements
- Replace the routes' direct `db.query(Project)` writes with `services/project_service.py::archive_project / restore_project / soft_delete_project`. Keeps service boundary clean.

---

### backend/app/api/agent_workflows.py
**Purpose:** Start + monitor BMAD workflows; SSE streaming; approve/reject signals.
**Reviewed lines:** 332.

#### Issues
- 🟠 **HIGH** lines 145-157: `read_workflow_artifact` reads files from disk based on `path` query param. The guard (`allowed_paths` set from `step.get("artifact_path")`) is correct but case-sensitive on Linux and case-insensitive on Windows — a request for the same logical file with different case bypasses the check on Linux while succeeding on Windows. Normalize via `os.path.normcase(os.path.realpath(p))` before comparison.
- 🟠 **HIGH** lines 145-157: the file read is synchronous (`open(...).read()`) inside an `async def`. For a slow disk it blocks the event loop. Use `aiofiles` or `await loop.run_in_executor`.
- 🟠 **HIGH** lines 204-222: SSE generator polls every 1s for up to 2 minutes (`for _ in range(120)`). For a long workflow that exceeds 2 minutes, the client gets a `timeout` event and must reconnect. Acceptable as MVP but no auth-on-reconnect mechanism is documented. Also the loop calls `await get_workflow_status(workflow_id, db=db)` which **opens a fresh DB query every second** — heavy under load. Use a pubsub channel (`asyncio.Queue` populated by a workflow event handler).
- 🟠 **HIGH** lines 248-260, 277-289: `signal_approve` / `signal_reject` connect to Temporal via `Client.connect(os.getenv("TEMPORAL_ADDRESS", "localhost:7233"))` — uses the env var directly instead of `settings.TEMPORAL_ADDRESS`. Inconsistent and bypasses the centralised config.
- 🟡 **MED** lines 86-96: `_assert_workflow_in_org` does a separate `db.query(WorkflowRun)` after every endpoint's own `get_workflow_status` call. Two DB round-trips per request.
- 🟡 **MED** lines 192-231: the SSE endpoint has no auth via query-string token (compare with `sprints.py::api_executions_stream` which does). Browsers can't send Authorization on EventSource — this endpoint is *unreachable* from a browser EventSource without proxy support. Either accept `?token=` (like sprints does) or document this is for `fetch + ReadableStream` consumers only.
- 🟡 **MED** lines 211-213: `data = json.dumps({"type": "step", "step": step})` — `step` comes straight from `get_workflow_status` which may include `parsed_output_json` (a dict). If any value isn't JSON-serializable (`datetime`, `UUID`), `dumps` raises and the generator dies. Add `default=str`.
- 🔵 **LOW** line 245-247: `import os` + `from temporalio.client import Client` inside the route handler — move to top.

---

### backend/app/api/artifacts.py
**Purpose:** Artifact upload + list + get.
**Reviewed lines:** 53.

#### Issues
- 🟡 **MED** lines 16-29: `upload_artifact` reads the whole upload into memory (`content = await file.read()`) before calling `validate_upload`. With `MAX_UPLOAD_MB=25` that's 25 MB per request × concurrency limit. Stream to disk + size-check incrementally.
- 🟡 **MED** line 22: `validate_upload` is called *after* the read. Move it before the disk write (already does), but consider checking `file.size` against the limit prior to read (FastAPI exposes `file.size`).
- 🟡 **MED** lines 32-43: `api_list_artifacts` paginates in Python again (same N+1-ish issue as projects).
- 🔵 **LOW** line 46-48: `api_get_artifact` returns 404 via service but takes no `project_id` — so a caller can fetch any artifact they have an org for. Fine, but document.

---

### backend/app/api/code_reviews.py
**Purpose:** Ad-hoc artifact analysis + review via BMAD agent Amelia.
**Reviewed lines:** 172.

#### Issues
- 🟠 **HIGH** lines 33-49: `_read_artifact_content` opens the artifact via `artifact.storage_path` with NO path validation. A malicious DB row could point at `/etc/passwd`. The artifact is created from `save_artifact_file` which itself validates, so today's data is safe — but anyone with DB write access (compromised service account) could mutate `storage_path` to escalate. Add `_assert_inside_storage_root` here too.
- 🟡 **MED** lines 52-65: `_get_latest_version` orders by `version_number.desc()` — same lexicographic-sort bug as `artifact_version_service` (version "10" < "2").
- 🟡 **MED** lines 86-118: `_run_bmad_review` instantiates a fresh `HelixBMAD()` per request and calls `helix.review_artifact(...)` synchronously inside a sync route. Heavy LLM call blocks the request worker. Convert to async + background task (return 202 + poll), or document the expected latency.
- 🔵 **LOW** lines 88-94: `requirement_text=filename` — using the filename as the requirement text is a hack to satisfy BMAD's API. Make `review_artifact` accept its own context.

---

### backend/app/api/validation.py
**Purpose:** Validation rule CRUD + run creation + recon run.
**Reviewed lines:** 107.

#### Issues
- 🟠 **HIGH** lines 60-75: `start_validation` creates the `ValidationRun`, then **schedules** `execute_validation_run` via `BackgroundTasks` passing the **request-scoped `db: Session`**. Background tasks run *after the response is sent*, by which point the request's session is closed by `get_db`'s `finally`. Any DB write inside `execute_validation_run` will fail. Use `SessionLocal()` inside the background task.
- 🟡 **MED** line 32: `create_rule` lacks any audit log entry.
- 🟡 **MED** line 53: `data: ValidationRunCreate = None` — same default-None bug as elsewhere; FastAPI will materialise an empty body, but it's brittle.
- 🟡 **MED** lines 96-107: `start_recon` catches `Exception` and returns HTTP 502 with the raw exception string. Leaks DB error messages / connection details to the client. Wrap to a generic error + log the original.

---

### backend/app/api/audit.py
**Purpose:** Audit log persistence + listing + CSV/PDF export + chain integrity verify.
**Reviewed lines:** 209.

#### Issues
- 🟠 **HIGH** lines 30: `_compute_entry_hash` HMACs using `settings.JWT_SECRET_KEY` — same secret used to sign JWTs. Rotating the JWT secret will break the entire audit chain verification. Use a dedicated `AUDIT_HMAC_KEY`.
- 🟠 **HIGH** lines 43-63: `write_audit` performs `ORDER BY created_at DESC LIMIT 1` to find the previous entry. Under concurrent writes two callers can read the same `prev_hash` and both write rows that claim to follow the same predecessor — the chain forks. Take an advisory lock (`SELECT pg_advisory_xact_lock('audit:' || org_id)`) or use a serial sequence column.
- 🟠 **HIGH** lines 50-58: audit log's `created_at` uses the DB server default (`func.now()`), so the row created inside `write_audit` doesn't yet have a `created_at` until `flush()`. The chain ordering relies on `created_at`, but two rows with identical microsecond timestamps tie-break arbitrarily.
- 🟡 **MED** lines 56-57: `event_metadata=json.dumps(meta) if meta else None` — `meta` can include the `config` (from `connectors.py::api_test_connection`). Even though `_safe_config` strips known credential keys, anything unknown (custom_key=secret) survives. Allowlist instead of denylist.
- 🟡 **MED** line 19: `_compute_entry_hash` payload omits `event_metadata` and `ip_address` — tampering with those fields is undetectable. Include them in the canonical payload.
- 🟡 **MED** lines 86-98: `list_audit_logs` returns hashes but never includes `event_metadata` in the response. Auditors want to see *what* the actor did, not just that they did something.
- 🔵 **LOW** lines 137-179: PDF export silently truncates `actor_id` / `entity_id` to 20 chars. For UUIDs that's the prefix only — confusing on long lists.

---

### backend/app/api/system.py
**Purpose:** Admin-gated system health, worker, failed-job listing.
**Reviewed lines:** 64.

#### Issues
- 🟠 **HIGH** lines 25-32: `_check_temporal` does a raw TCP `socket.create_connection` against `host:port`. (a) does not actually verify Temporal protocol, only port open; (b) `settings.TEMPORAL_ADDRESS.split(":")` blows up on IPv6 addresses like `[::1]:7233`. Use temporalio's `Client.connect(...)` with a timeout.
- 🟡 **MED** lines 57-59: `worker_status` is a stub returning `{"workers": [], "status": "no workers connected"}` regardless. Document explicitly that this is unimplemented (or remove until wired).
- 🟡 **MED** lines 62-64: same — `failed_jobs` is a stub.
- 🔵 **LOW** line 50: `storage_ok` is computed via `os.path.exists` — symlink loops or filesystem stalls can hang the request.

---

### backend/app/api/connectors.py
**Purpose:** Stateless connector test + discovery endpoints; SSRF guard.
**Reviewed lines:** 191.

#### Issues
- 🟠 **HIGH** lines 47-104: SSRF guard is a good start but has gaps. (1) `_resolve_host` strips schemes but only common ones — `jdbc://`, custom schemes pass through unstripped. (2) `socket.getaddrinfo` does a blocking DNS lookup inside an `async def` — blocks the loop. Use `loop.getaddrinfo`. (3) IPv6 link-local + cloud metadata equivalents on GCP (`metadata.google.internal` → `169.254.169.254`) are blocked, but Azure's `169.254.169.254` redirect and DigitalOcean's metadata IP `169.254.169.254` use the same address; OK. (4) The check runs once, but DNS can re-resolve to an internal IP between check and connect ("DNS rebinding"). Either resolve to an IP and pass that IP to the connector, or repeat the check inside the connector.
- 🟠 **HIGH** lines 39-41: `DiscoveryRequest.config: dict` is a free-form dict accepted from the client. Combined with the SSRF guard's denylist nature, an attacker can probe internal services via fields the guard doesn't know about (e.g. `master_host`, `replica_url`). Move to a per-connector typed config schema.
- 🟡 **MED** lines 117, 122-126: audit logs the entire `config` (after `_safe_config`). Sensitive keys outside the denylist still flow through. (See `audit.py` finding above.)
- 🟡 **MED** lines 73-77: `socket.getaddrinfo(s, None)` — port=None returns *all* socktypes. Filter for AF_INET / AF_INET6 explicitly.
- 🔵 **LOW** lines 55: `_ALLOW_PRIVATE = os.environ.get(...)` is read once at import time. Toggling it requires restart.

---

### backend/app/api/encryption.py
**Purpose:** Admin endpoint to rotate per-org DEK.
**Reviewed lines:** 19.

#### Issues
- 🟡 **MED** line 12: `@router.post("/admin/org/rotate-dek")` — no audit log entry written. Key rotation is one of the most security-relevant events; it MUST be audited.
- 🟡 **MED** line 18: `rotate_dek` runs synchronously inside the request. For an org with many encrypted blobs this is fine because rotation doesn't re-encrypt anything (services/envelope_encryption_service.py:73 — "Re-encrypt secrets separately"). The endpoint should make that limitation explicit in the docstring.

---

### backend/app/api/invitations.py
**Purpose:** Invite users to an org, accept invites, list/revoke.
**Reviewed lines:** 110.

#### Issues
- 🟡 **MED** lines 24-43: `_INVITABLE_ROLES` includes `developer` and `analyst`, but `auth_service.py::SYSTEM_ROLES` only seeds `super_admin / admin / project_manager / architect / data_engineer / qa_engineer / viewer`. Inviting someone as `developer` will fail at `invitation_service.create_invitation` (line 55) when the role lookup returns None — and the service falls through, persisting `role_id=None`. Silent demotion. Keep these lists in sync.
- 🟡 **MED** line 66: `invite_url` is built from `settings.FRONTEND_URL` + path + `?token=` — but `FRONTEND_URL` defaults to `http://localhost:3000`. Production deploys often forget to set this; the email links then point at localhost. Add a startup check.
- 🟡 **MED** line 75-78: `accept_invite` is unauthenticated (no `Depends`) and rate-limited to `10/minute`. Limiter is disabled in dev. Brute-force the 32-byte token space is infeasible, but a more conservative cap (3/minute) is cheap insurance.
- 🔵 **LOW** line 78: `invite_user` writes no audit entry on success. The act of inviting someone *is* an admin action — audit it.

---

### backend/app/api/webhooks.py
**Purpose:** Webhook CRUD + delivery listing.
**Reviewed lines:** 136.

#### Issues
- 🟠 **HIGH** lines 60-85: `update_webhook` uses `if data.url:` / `if data.events:` — these treat empty string as "don't update", which is **inconsistent** with Pydantic's default-None semantics elsewhere. If a user wants to *clear* the events list (i.e. set to empty), they can't. Use `if data.url is not None:`.
- 🟠 **HIGH** lines 31, 84-86: `WebhookCreate.url: str` accepts any string. The actual URL is dispatched to via `httpx.AsyncClient.post(ep.url, ...)` in `webhook_service.deliver_webhook`. Combined with no SSRF guard on webhook URLs, an admin can register `http://169.254.169.254/latest/meta-data/iam/security-credentials/` as a webhook endpoint and exfiltrate AWS credentials via the webhook payloads. Apply the same `_enforce_host_allowlist` (or a dedicated webhook policy) here.
- 🟡 **MED** line 22-25: schema uses `url: str` but the Pydantic import shows `HttpUrl` was intended (line 3). Use `HttpUrl` to at least reject non-URL inputs.
- 🟡 **MED** lines 28, 38, 65, 92, 107: requires `admin:llm:read / write` permission — semantically wrong. Should be `admin:webhooks:read / write`. Reusing the LLM permission as a catch-all for "admin only" makes RBAC unusable for least-privilege.

---

### backend/app/api/usage.py
**Purpose:** Per-org API usage stats (24h / 7d / 30d audit counts).
**Reviewed lines:** 61.

#### Issues
- 🟡 **MED** lines 26-50: three separate queries against `audit_logs` per call — for a long-retention org this is slow. Compute all three windows in a single query with `CASE WHEN`.
- 🟡 **MED** line 35: `top_actors` GROUP BY `actor_id` — null actor_ids (system events) get bucketed together. Filter them out or label as "system".

---

### backend/app/api/superadmin.py
**Purpose:** Platform-level admin operations: list orgs, suspend orgs, impersonate, stats.
**Reviewed lines:** 105.

#### Issues
- 🔴 **CRITICAL** lines 73-92: `impersonate_user` issues a 15-min JWT for the target user. The token is identical in structure to a normal user token — there's **no `impersonator` claim** in the JWT, so downstream audit logs show the action as performed by the target user, not the impersonating super-admin. The log line at 86-88 is the only trail. If the JWT is exfiltrated mid-15-minute window, post-hoc forensics see the *target* user's id. Embed `imp_by` in the token + propagate to `write_audit` via the `actor_id` chain.
- 🟠 **HIGH** lines 41-55: `set_org_status` accepts `status` as a query parameter (not body). Easy to log into URL logs / proxy logs / browser history. Move to body.
- 🟡 **MED** line 33: `member_count` is computed via N+1 — one `COUNT(*)` query per org. Use a `JOIN ... GROUP BY` or a subquery.
- 🟡 **MED** lines 96-105: `platform_stats` runs four `COUNT(*)` queries serially; combine into a single `SELECT (SELECT count(*) FROM orgs), (SELECT count(*) FROM users), ...`.
- 🟡 **MED** the entire router has zero `write_audit` calls. Every super-admin action (org suspend, impersonate, status change) must be audited.

---

### backend/app/api/users.py
**Purpose:** Profile + preferences CRUD for the calling user.
**Reviewed lines:** 75.

#### Issues
- 🟡 **MED** lines 56-75: `update_my_preferences` serialises the full preferences dict + 16 KiB ceiling. The 16 KiB check happens after the merge — if the merge result exceeds, the request fails *but* `current.update(data.preferences)` already mutated the local dict (no DB write yet, so OK). Worth a comment.
- 🟡 **MED** line 73: `flag_modified(user, "preferences")` — correct workaround for JSON column mutation tracking. Good.
- 🔵 **LOW** no audit entry on profile or preferences update. UX-only changes are arguably not audit-worthy; security-relevant ones (email, password) are routed through other endpoints. OK.

---

### backend/app/api/sprints.py
**Purpose:** Sprint Management read API + a few mutations + SSE stream for executions + admin seed.
**Reviewed lines:** 333.

#### Issues
- 🟠 **HIGH** lines 98-164: `api_executions_stream` accepts a JWT via `?token=` because EventSource can't send headers. The token is decoded inline and `resolve_active_org_id` applied. Good. But: the SSE generator runs `list_executions(db, ...)` **every 2 seconds for up to 5 minutes**, holding the request-scoped `db: Session` open the whole time. SQLAlchemy sessions aren't designed to live that long; long-running idle transactions can block migrations or cause MVCC bloat. Open a fresh `SessionLocal()` per poll and dispose.
- 🟠 **HIGH** lines 269-281: `api_patch_task` accepts a full `SprintTaskUpdate` but only honours `status`. Other fields silently ignored — confusing. Either implement them or reject the request when non-status fields are present.
- 🟡 **MED** line 47: many endpoints lack a `user_id` resolution and write no audit. Sprint mutations (create_sprint, create_task, decide_approval, seed) do audit; reads correctly don't. Patch_task doesn't audit — should, for status transitions.
- 🟡 **MED** lines 305-333: `api_seed_sprints` is admin-gated via `require_permission("admin:llm:write")` — same RBAC-reuse problem as webhooks.py. Sprints are not LLM.
- 🔵 **LOW** lines 109-122: the stream auth error catches `Exception` and rethrows as 401 — masks bugs like a DB outage as "Invalid stream token". Narrow the catch.

---

### backend/app/services/auth_service.py
**Purpose:** First-admin bootstrap, login, permission/role seed.
**Reviewed lines:** 107.

#### Issues
- 🟠 **HIGH** line 57-86: `setup_first_admin` mixes data-bootstrap (seed_permissions, seed_roles) with the actual user creation in one big transaction. If anything in the middle fails, partial state remains because the function `commit()`s twice (line 65: `flush` — fine; line 83: `commit`, after which earlier `flush`es become durable). Wrap the whole thing in a single `with db.begin()`.
- 🟠 **HIGH** line 58: `db.query(User).filter(User.is_super_admin == True).first()` — race window between this check and `db.add(user)` allows two concurrent first-admin setups to both succeed (different orgs). Use a serializable transaction or a unique partial index `WHERE is_super_admin = true`.
- 🟡 **MED** line 91-100: `login` is rate-limited at the route layer (10/min by IP). No per-account lockout — credential-stuffing across accounts from rotating IPs is unmitigated.
- 🟡 **MED** lines 25-32: `SYSTEM_ROLES` lists 7 roles but `invitations.py::_INVITABLE_ROLES` lists `viewer / editor / developer / analyst` — `editor / developer / analyst` are not in `SYSTEM_ROLES`. Inconsistency.
- 🟡 **MED** line 27: super_admin gets `"*"` which `seed_roles` expands to `db.query(Permission).all()`. But `seed_permissions` runs *before* `seed_roles`, so this is fine. However the relation is fragile — if a permission is added after first-admin seed, super_admin won't auto-pick it up. Re-seed roles on app startup or add a post-migration hook.
- 🔵 **LOW** line 89-100: `login` writes no audit entry for failed attempts. Failed logins are a critical security signal.

---

### backend/app/services/password_reset_service.py
**Purpose:** Issue + validate + apply password reset tokens.
**Reviewed lines:** 69.

#### Issues
- 🟡 **MED** lines 25-43: `request_password_reset` allows unlimited active reset tokens per user. An attacker who triggers reset via the public endpoint can spam-create rows. The endpoint is rate-limited (5/min), but DB growth + cleanup are still concerns. Invalidate prior active tokens when a new one is created.
- 🟡 **MED** lines 46-69: `confirm_password_reset` does *not* invalidate the user's outstanding JWTs. After password reset, the old JWT (issued before the reset) is still valid until natural expiry. Either bump a `password_changed_at` field and reject older tokens, or revoke all of the user's tokens in Redis.
- 🟡 **MED** line 66: no minimum password strength check on the new password.

#### Improvements
- Hash tokens via `secrets.compare_digest` to avoid timing leaks (currently just `==` on hashed values, which is OK because hashes have uniform length — minor nit).

---

### backend/app/services/invitation_service.py
**Purpose:** Create + accept + list + revoke invitations.
**Reviewed lines:** 144.

#### Issues
- 🟠 **HIGH** lines 89-91: `invite.expires_at < datetime.now(timezone.utc)` — if `OrgInvitation.expires_at` is `naive` (no tz), this throws `TypeError`. The migration creates the column as `DateTime(timezone=True)` so Postgres returns aware datetimes. Fine — but on SQLite tests (none configured today) it'd break.
- 🟠 **HIGH** lines 102-115: invitation acceptance creates a user *and* a membership in one commit. If two callers accept the same invite concurrently, both pass the `status == "pending"` check and both add memberships. Use a serializable transaction or `UPDATE ... WHERE status = 'pending' RETURNING ...`.
- 🟡 **MED** lines 107-109: `default_role = db.query(Role).filter(Role.id == invite.role_id).first() if invite.role_id else db.query(Role).filter(...).first()` — fallback to "viewer" by name. If the org somehow lacks a "viewer" role, `default_role = None` and membership is created with `role_id=None` — broken state. Raise explicitly.
- 🟡 **MED** line 32-33: no email format validation (Pydantic validates at the API boundary; this service can be called from background tasks). Defence in depth.

---

### backend/app/services/email_service.py
**Purpose:** SMTP + SendGrid send; HTML templates.
**Reviewed lines:** 143.

#### Issues
- 🟠 **HIGH** lines 87-101 / 105-122 / 125-144: HTML templates use f-string interpolation directly into HTML. `inviter_name`, `org_name`, `project_name` flow in from request bodies — **HTML injection** possible. Use `markupsafe.escape` or `jinja2`.
- 🟡 **MED** lines 31-55: SendGrid path is `async with httpx.AsyncClient() as client` — re-opens a client per send. For high-volume sends this is wasteful; use a module-level client.
- 🟡 **MED** line 53: `logger.error("SendGrid delivery failed ...")` logs the response body up to 200 chars. SendGrid error payloads may include API key snippets in some scenarios — sanitize.
- 🟡 **MED** lines 58-79: SMTP path opens a new connection per send. Same as SendGrid.
- 🔵 **LOW** line 22: `EMAIL_DISABLED` log includes the subject; subjects sometimes contain entity ids — small PII consideration.

---

### backend/app/services/project_service.py
**Purpose:** Projects + subprojects + requirements + connection (source/target) CRUD with config encryption.
**Reviewed lines:** 301.

#### Issues
- 🟠 **HIGH** lines 83-86: `_SENSITIVE_KEYS` is a fixed denylist (`password / secret / token / api_key / access_key / access_key_id / secret_access_key / client_secret / private_key / passphrase`). Connector configs include things like `auth_token`, `bearer`, `signing_key` that are NOT in this list. Result: those values flow into the masked preview unredacted. Switch to a **value-shape-based** redactor (mask anything >= 16 chars that looks high-entropy) OR an allowlist of `safe_keys`.
- 🟠 **HIGH** lines 114-120: `_encrypt_config` returns `("", "")` for an empty config. Callers (line 181) check `or None`, fine. But `_decrypt_config` on `""` returns `{}` silently — losing the distinction between "no config" and "encryption failure". `decrypt_value("")` raises `ValueError`, but the `if not encrypted: return {}` short-circuits before that. OK by design, just document.
- 🟡 **MED** line 27: `create_project` does not record an audit entry (route does). Fine — but the function name suggests it would.
- 🟡 **MED** lines 274-286, 290-302: `add_table` / `add_column` use a join through `Project` for org-scope verification. Good. But they do two round-trips (verify then insert). Use a single CTE or trust the verify and skip the refresh.
- 🔵 **LOW** lines 211-214: `delete_source` / `delete_target` use `db.delete(conn)` — cascades not declared on FK; orphan schemas in `schemas.source_connection_id` survive (but they're nullable, so it's fine).

---

### backend/app/services/secret_service.py
**Purpose:** Fernet encrypt/decrypt + API key masking.
**Reviewed lines:** 33.

#### Issues
- 🟠 **HIGH** lines 9-11: `Fernet(base64.urlsafe_b64encode(hashlib.sha256(KEY.encode()).digest()))` — deterministically derives a Fernet key from the master `ENCRYPTION_KEY` via SHA256. This is correct ENVELOPE for the simple-secret path, **but** because Fernet uses a 128-bit AES key plus 128-bit HMAC key concatenated, you're feeding 32 raw bytes through `urlsafe_b64encode` → 44 chars (right size). It works, but the key derivation is not a KDF — no per-secret salt, no per-org isolation in the simple path. Combine with the per-org DEK service for proper isolation.
- 🟡 **MED** line 14: `encrypt_value` raises on empty input — but `encrypt_for_org` (in `envelope_encryption_service.py`) does NOT. Consistent API for both encryption paths is preferable.
- 🟡 **MED** lines 28-33: `mask_key("sk-very-short")` may not behave as expected — examines `len <= visible_chars * 2`. For short keys returns `"*" * len(key)` instead of first 4 + middle stars + last 4. Add a unit test.

---

### backend/app/services/envelope_encryption_service.py
**Purpose:** Per-org DEK encrypted with master KEK.
**Reviewed lines:** 92.

#### Issues
- 🟡 **MED** lines 37-57: `_get_or_create_dek` reads then writes inside an autocommit boundary — two callers in parallel can both miss the read, both generate a DEK, both insert, and the unique constraint on `organization_id` will reject the second. The exception isn't caught. Wrap in advisory lock or `INSERT ... ON CONFLICT DO NOTHING`.
- 🟡 **MED** lines 72-92: `rotate_dek` deactivates the old DEK and creates a new one, but the *existing ciphertexts* are still encrypted with the old DEK. Once `is_active=False`, future `_get_or_create_dek` calls return the **new** DEK; decryption of old ciphertexts now fails. The docstring on `encryption.py` says "Re-encrypt secrets separately after rotation", but there's no helper to do that. Rotation is a footgun without it.
- 🟡 **MED** line 39: `db.query(...).filter(... is_active == True).first()` — `is_active == True` should be `is_(True)` to avoid SQLAlchemy warning on some dialects.

#### Improvements
- Cache the per-org plaintext DEK in memory (with TTL) so high-throughput callers don't repeatedly hit the DB.

---

### backend/app/services/connector_service.py
**Purpose:** Factory + dispatch over built-in + custom connectors.
**Reviewed lines:** 94.

#### Issues
- 🟡 **MED** line 41: `cls = BUILTIN_CONNECTORS.get(ConnectorType(connector_type))` — if `connector_type` is "postgres" it works, but for custom string types the `ConnectorType(connector_type)` raises `ValueError` (not in enum). The fallthrough only happens for raised exceptions on the second `.get` line, so a bad custom type produces an unhelpful `ValueError`. Try/except the enum cast.
- 🟡 **MED** every function creates a fresh connector instance per call. For SQL connectors with `_engine` lazy init this is wasteful — engines get garbage-collected immediately. Cache `(connector_type, hash(config))` → connector.
- 🔵 **LOW** line 86: `from connectors.custom.registry import list_registered_connectors` is imported inside the function — minor; move to top.

---

### backend/app/services/llm_router_service.py
**Purpose:** Provider type enum + agent type list + simple routing resolver.
**Reviewed lines:** 36.

#### Issues
- 🟡 **MED** line 31-36: `resolve_routing` returns hard-coded `0.7, 4096` for the fallback case, ignoring the *provider's* `temperature / max_tokens`. Fall back to the provider's defaults, not literals.
- 🔵 **LOW** line 21-28: `AGENT_TYPES` is a list of strings; `LLMProviderType` is an enum. Why not both enums or both lists?

---

### backend/app/services/llm_provider_service.py
**Purpose:** Provider CRUD + key rotation + agent mapping.
**Reviewed lines:** 232.

#### Issues
- 🔴 **CRITICAL** line 91: `rotated_at=str(uuid.uuid4())` writes a UUID into a column meant to hold a timestamp string. Pure bug — operators can't tell when a key was rotated. Replace with `datetime.now(timezone.utc).isoformat()`.
- 🟠 **HIGH** lines 19-43: `create_provider` doesn't check whether `api_key` is empty. For Bedrock / Vertex (IAM / ADC auth), `api_key` is intentionally blank. `encrypt_value` raises on empty (`secret_service.py` line 16). So creating a Bedrock provider crashes. Either pre-empt the empty-string check or skip encryption when the key is empty.
- 🟠 **HIGH** lines 206-232: `_to_response` decrypts the API key, masks it, returns. Decryption per list call × N providers = N decrypt operations. For an org with many providers this is wasteful and exposes the decrypted value in process memory needlessly. Pre-compute the masked form at write time and store alongside the ciphertext (you already do this for connection configs).
- 🟡 **MED** lines 75-95: `rotate_key` doesn't deactivate the previous secret — multiple "active" rows exist with different versions. `test_connection` (line 109) picks the highest version, which works, but the rotation history isn't queryable.
- 🟡 **MED** lines 167-203: `replace_agent_mappings` validates providers then deletes all then inserts. If one of the inserts fails (FK violation), the org loses *all* mappings. Wrap in a savepoint / use `db.begin_nested()`.

---

### backend/app/services/llm_provider_adapters.py
**Purpose:** Per-provider test-connection adapters (HTTP or SDK).
**Reviewed lines:** 258.

#### Issues
- 🟡 **MED** line 137: `BedrockAdapter` reads `aws_access_key_id` from `extra_config` directly (plaintext). `extra_config` is `Column(JSON, nullable=True)` on `LLMProvider`, **not encrypted**. So AWS access keys saved here live in plaintext in the DB. Either encrypt the value or document this as "for IAM-role flows only".
- 🟡 **MED** line 91-93: `GeminiAdapter` embeds the API key in the URL (`?key={api_key}`). Server-side logs and DNS-level intermediaries (corporate proxies) see the key in cleartext.
- 🟡 **MED** lines 218-234: factory falls through to `OpenAICompatibleAdapter` for unknown provider types. Easy to overlook; log a warning.
- 🔵 **LOW** line 188: `api_version = cfg.get("api_version", "2026-01-01")` — hard-coded fallback API version. As Azure rolls forward, this will go stale.

---

### backend/app/services/workflow_service.py
**Purpose:** Bridge BMAD workflows to FastAPI; persist runs + steps.
**Reviewed lines:** 388.

#### Issues
- 🟠 **HIGH** lines 35-102: `start_bmad_planning_workflow` tries Temporal then falls back to local in dev. The fallback runs the entire LangGraph in-process with `helix.run()` — *synchronously inside an `async def`*. For a multi-agent planning workflow that's many seconds → minutes of event-loop blocking. Use `await asyncio.to_thread(helix.run)`.
- 🟠 **HIGH** lines 70-81: bare `except Exception` to catch Temporal connection issues. Real bugs in `helix.start_temporal()` (programming errors, AttributeError) are swallowed in dev and trigger the fallback. Narrow to specific exceptions (`RuntimeError`, `temporalio.client.RPCError`).
- 🟠 **HIGH** lines 217-289: `_persist_workflow_result` re-reads each artifact file (`open(paths_for_agent[-1], "r", encoding="utf-8")`) to extract `llm_mode` / `model` from YAML frontmatter. (a) sync IO inside the same call chain that already ran the workflow; (b) per step, an open+read happens on the request path. Read once at workflow finish, not per-step. Better: have BMAD return the provenance directly.
- 🟡 **MED** lines 30-32: `APP_ENV = os.getenv("APP_ENV", "development")` — bypasses `settings.APP_ENV`. Inconsistent.
- 🟡 **MED** lines 126-127: when `WorkflowRun` is not found, the function infers `mode` from substring `"bmad-"` in the id. Hacky; if a future workflow id format changes, this misclassifies. Return `mode="unknown"` instead.
- 🟡 **MED** line 195-198: rollback on exception is correct, but the `own_db` flag-and-rollback pattern is duplicated. Extract to a context manager.

---

### backend/app/services/artifact_version_service.py
**Purpose:** Artifact metadata + version queries.
**Reviewed lines:** 68.

#### Issues
- 🟡 **MED** lines 33-38: `list_artifacts` has no pagination — returns ALL artifacts for the project. Route paginates in Python; push it into the query.
- 🟡 **MED** lines 65: `order_by(CodeArtifactVersion.version_number.desc())` — lexicographic, same bug as elsewhere.
- 🟡 **MED** lines 12-31: `create_artifact_metadata` always inserts version "1". Subsequent uploads of the same filename get a new artifact row (not a new version of the same artifact). Decide which semantic you want and document.

---

### backend/app/services/validation_service.py
**Purpose:** Execute validation runs across rules.
**Reviewed lines:** 138.

#### Issues
- 🟠 **HIGH** lines 59-138: `execute_validation_run` is called via `BackgroundTasks` with a request-scoped session. After the response ships, the session is closed. Every `db.commit()` inside this function fails silently for any sufficiently-long-running rule. Open a fresh `SessionLocal()` here.
- 🟠 **HIGH** lines 89: `defn = json.loads(rule.definition)` — `definition` is user-supplied. Combined with `defn.get("source_config", {})` flowing straight into a connector that opens a network connection, the SSRF guard on `connectors.py` is **bypassed** for rules created via the validation router. Add the same `_enforce_host_allowlist` here.
- 🟡 **MED** lines 76-86: row-count rule reads connector type/schema/table from a `connector_configs` dict passed at run time. No validation; a malformed dict silently yields `connector_type="postgres"` (default) and an empty schema/table.
- 🟡 **MED** lines 123-134: catches `Exception` broadly. At minimum log it (already does) but also include the rule_id in the persisted error.

---

### backend/app/services/recon_service.py
**Purpose:** Row-count reconciliation between source and target.
**Reviewed lines:** 84.

#### Issues
- 🟠 **HIGH** lines 39-50: connectors receive `source["config"]` / `target["config"]` directly from the request body via `validation.py::start_recon`. **No SSRF guard.** Same issue as validation_service. Wrap with `_enforce_host_allowlist`.
- 🟡 **MED** lines 23-30: `recon_run` is created but has no FK to project (model uses `String(36)` without `ForeignKey`). Orphans on project delete.
- 🟡 **MED** line 7: `import uuid` is unused.
- 🔵 **LOW** line 55: `import json` inside the try block — hoist.

---

### backend/app/services/webhook_service.py
**Purpose:** HMAC-signed webhook delivery.
**Reviewed lines:** 73.

#### Issues
- 🟠 **HIGH** line 37: `async with httpx.AsyncClient(timeout=10) as client:` then iterates endpoints serially. If one endpoint is slow, all subsequent endpoints in the same delivery wait. Fan out with `asyncio.gather`.
- 🟠 **HIGH** lines 62-70: failure handling — `except Exception` swallows everything; `delivery.error = str(exc)[:255]` truncates the exception. No retry, no dead-letter, no backoff. Webhooks need at-least-once semantics; this is fire-and-forget.
- 🟡 **MED** line 35-36: `body = json.dumps({...}).encode()` — if `payload` contains non-JSON types (datetime, UUID), `dumps` raises. Pass `default=str`.
- 🟡 **MED** lines 39-41: `events_list = [e.strip() for e in ep.events.split(",")]` — see webhook model note about comma-separated events.

---

### backend/app/services/sprint_service.py
**Purpose:** Sprint Management CRUD + derived velocity / burndown.
**Reviewed lines:** 341.

#### Issues
- 🟠 **HIGH** lines 26-51: `create_sprint`'s `last_index` is computed via `count()` not `max(index)`. With gaps (e.g. deleting sprint 2), counts diverge from max+1. Use `coalesce(max(index), 0) + 1`.
- 🟠 **HIGH** lines 26-51: indexes aren't guarded against concurrent inserts — two API calls hit `count() = 5`, both insert index 6. Add a unique constraint or use `INSERT ... SELECT ... RETURNING`.
- 🟡 **MED** lines 222-233: `get_mapping_graph` returns lists by `db.query(...).all()` without explicit ordering — the canvas position randomness changes each fetch.
- 🟡 **MED** lines 268-341: `compute_burndown` is heavy: loads all tasks + all history rows + iterates per day in Python. For a large sprint (180 days × hundreds of tasks) this becomes slow. Push to a SQL aggregate.
- 🟡 **MED** line 339: `actual_remaining = total - cumulative_done if d <= today else total - cumulative_done` — both branches identical. Likely a left-over of an earlier divergence; either remove or restore the difference (future days should show "no data" / extrapolation).
- 🔵 **LOW** line 215: `.order_by(MigrationRelease.scheduled_for.asc().nullslast())` — `nullslast()` is Postgres-specific; works with SQLAlchemy 2.x but flag for cross-DB plans.

---

### backend/app/services/sprint_seed.py
**Purpose:** Deterministic demo seed of Sprint Management dataset.
**Reviewed lines:** 296.

#### Issues
- 🟡 **MED** lines 61-84: `_seed_clean` runs four `DELETE` calls with `synchronize_session=False` then a fifth `db.query(Sprint).delete(...)` that relies on FK cascades for tasks/risks/approvals. If a cascade isn't actually defined at DB level (Postgres `ondelete="CASCADE"` is set in the migration, but bare `String(36)` on `Sprint.id` references project's id with cascade), the cleanup may leave orphans. Test on a fresh DB.
- 🟡 **MED** lines 92-127: hard-coded `datetime(2026, 4, 6, …)` will make seeds look stale a year later. Use `datetime.now(timezone.utc) - timedelta(days=14*i)`.
- 🔵 **LOW** lines 218-230: tuple unpack with 12 fields is fragile to ordering changes. Use a TypedDict or dataclass.

---

### connectors/base/connector.py
**Purpose:** Abstract base + dataclasses for connector contract.
**Reviewed lines:** 151.

#### Issues
- 🟡 **MED** line 125: `capabilities: ConnectorCapabilities = field(default_factory=ConnectorCapabilities)` is a class-level attribute using `dataclasses.field` — but `BaseConnector` is **not** a dataclass. `field(default_factory=...)` outside a dataclass is just a `Field` object, not the dict-default fallback you'd expect. Subclasses override `capabilities` as a plain class attribute, which works (default is unused). Remove the `field(...)` call.

---

### connectors/base/identifiers.py
**Purpose:** SQL-identifier safety check.
**Reviewed lines:** 26.

#### Issues
- 🟡 **MED** line 6: pattern `[A-Za-z_][A-Za-z0-9_]*` rejects perfectly valid identifiers with `$` (Oracle, Snowflake) or `#` (SQL Server temp tables). For Helix's stated targets (Postgres / MySQL / Snowflake), `$` is needed. Add a comment that this is intentionally stricter than SQL spec.

---

### connectors/base/exceptions.py
**Purpose:** Connector-specific exceptions.
**Reviewed lines:** 25.

No findings.

---

### connectors/__init__.py
**Purpose:** Re-export public surface.
**Reviewed lines:** 24.

No findings.

---

### connectors/postgres/connector.py
**Purpose:** Postgres implementation.
**Reviewed lines:** 169.

#### Issues
- 🟠 **HIGH** lines 69-77, 79-88, etc.: `test_connection`, `list_schemas`, `list_tables`, etc., are declared `async def` but the body is **synchronous SQLAlchemy** (`self._get_engine().connect()`). They run on the event loop. Every database I/O blocks. Wrap in `asyncio.to_thread` or use the async dialect (`postgresql+asyncpg`).
- 🟠 **HIGH** line 145: `text(f'SELECT COUNT(*) FROM "{schema_name}"."{table_name}"')` — the f-string interpolation is safe **only because** `validate_identifier` was called above. If the validation is ever skipped or bypassed, this is SQL injection. Use SQLAlchemy's `quoted_name` or `Identifier` literally.
- 🟡 **MED** line 53-57: `_get_engine` creates one engine per `PostgreSQLConnector` instance. `connector_service` builds a fresh instance per call → engine churn. Cache.
- 🟡 **MED** line 76: `except Exception as exc: logger.warning(... %s, exc)` — exception text may include connection-string fragments depending on the driver. Today the URL is built without exposing the password (`quote_plus(password)`) but `psycopg2` errors sometimes echo connection params.
- 🔵 **LOW** line 60: `pool_pre_ping=True` is sensible.

---

### connectors/mysql/connector.py
**Purpose:** MySQL implementation.
**Reviewed lines:** 152.

#### Issues
- 🟠 **HIGH** same async-but-sync issue as Postgres.
- 🟠 **HIGH** line 51: `if not ssl_disabled: url += "?ssl_disabled=false"` — the parameter name is `ssl_disabled` but it's set to "false". The pymysql driver expects `ssl={...}` config, not `?ssl_disabled=false`. Likely a bug that does nothing; SSL isn't being requested at all even when intended.
- 🟡 **MED** line 143: `text(f"SELECT COUNT(*) FROM `{schema}`.`{table}`")` — same identifier-injection concern as Postgres (mitigated by `validate_identifier`).
- 🔵 **LOW** line 18: unused `ConnectionFailedError` import.

---

### connectors/sqlserver/connector.py
**Purpose:** SQL Server implementation.
**Reviewed lines:** 138.

#### Issues
- 🔴 **CRITICAL** line 44: `trust_cert = "no" if cfg.get("trust_server_certificate", False) else "no"` — both branches assign `"no"`. The intent was almost certainly `"yes" if cfg.get(...) else "no"`. As written, the user CANNOT enable `TrustServerCertificate` even when they need to (self-signed certs in dev). This is a typo bug.
- 🟠 **HIGH** async-but-sync (same).
- 🟡 **MED** line 134: identifier-injection mitigation via `validate_identifier`; safe given that.

---

### connectors/snowflake/connector.py
**Purpose:** Snowflake implementation.
**Reviewed lines:** 142.

#### Issues
- 🟠 **HIGH** async-but-sync (same).
- 🟡 **MED** line 96/118: passing `schema_name.upper()` for the parameterised query — works for unquoted Snowflake identifiers, but fails for case-sensitive (quoted) identifiers in source schemas. Snowflake users with mixed-case schemas will get empty results. Document or detect.
- 🟡 **MED** line 50: `?{'&'.join(params)}` — if `params` is empty, the URL ends without a query string (correct). If first param is `None`-equivalent (empty string), `quote_plus` returns "" — produces `warehouse=`. Filter empty values first.

---

### connectors/s3/connector.py
**Purpose:** S3 bucket listing + CSV/Parquet schema inference.
**Reviewed lines:** 127.

#### Issues
- 🟠 **HIGH** lines 41-53: when `cfg.get("role_arn")` is set, the code does `sts.assume_role(...)` and overwrites `kwargs` — but if the *original* `cfg["access_key_id"]` was set, it's now overwritten by the assumed creds (correct). However, if `role_arn` is set without an upstream `access_key_id`, the initial `sts = boto3.client("sts", **kwargs)` uses the instance profile / env / config-file creds — that's fine; just document the precedence.
- 🟠 **HIGH** lines 32-53: every method (`list_schemas`, `list_tables`, `list_columns`) calls `_get_client()` again. For role-arn flows that means **a fresh STS `AssumeRole` call per request**. Cache the assumed creds for `Credentials.Expiration - 60s`.
- 🟡 **MED** lines 110-122: schema inference reads only `bytes=0-4096`. CSVs with long header rows (>4 KB) get truncated headers and missing columns. Increase or stream until newline.
- 🟡 **MED** line 116: `header_line.split(",")` doesn't handle CSV quoting (a header `"foo, bar"` becomes two columns). Use `csv.reader`.
- 🟡 **MED** line 110: synchronous `boto3` call in async context. Same async-but-sync pattern.
- 🔵 **LOW** lines 90-93: file detection by extension only. Doesn't catch `.csv.gz`.

---

### connectors/files/csv_connector.py
**Purpose:** Local-FS CSV connector.
**Reviewed lines:** 98.

#### Issues
- 🟠 **HIGH** lines 87-95: `get_row_count` does `pd.read_csv(path)` — **loads the entire file into RAM** to count rows. For a 1 GB CSV that's 4-10 GB of pandas DataFrame overhead. Use a streaming counter (`sum(1 for _ in open(path)) - 1`).
- 🟠 **HIGH** lines 42-46: `_resolve_path` uses `os.path.exists(path)` without confining the path under a sandbox root. If the config arbitrarily points at `/etc/shadow.csv`, it'll read it. The artifact storage path is sandboxed by `app/storage/local.py`, but this connector accepts any path from a config dict. Tighten.
- 🟡 **MED** line 67-83: column inference uses `pd.read_csv(path, nrows=0)` — reads only the header but still loads via pandas; for malformed CSVs pandas raises a useful error but for very wide CSVs (10k+ columns) it's slow.

---

### connectors/files/excel_connector.py
**Purpose:** Local-FS Excel connector.
**Reviewed lines:** 103.

#### Issues
- 🟠 **HIGH** lines 96-97: same RAM blow-up as CSV — `pd.read_excel(path, sheet_name=sheet)` to count rows.
- 🟠 **HIGH** path confinement same as CSV.
- 🟡 **MED** line 64: `pd.ExcelFile(path)` opens the file synchronously and keeps a workbook in memory. For 100 MB Excel files this is slow.

---

### connectors/custom/registry.py
**Purpose:** Custom connector class registry.
**Reviewed lines:** 31.

No findings — minimal and correct.

---

### backend/alembic/versions/25b337c73f7a_identity_tables.py
**Purpose:** Initial identity tables (orgs, users, roles, permissions, memberships).
**Reviewed lines:** 83.

#### Issues
- 🟠 **HIGH** lines 20-74: uses `postgresql.UUID(as_uuid=True)` for primary keys + FKs. Models declare `String(36)` for `id` in `base.py`. **Type mismatch between migration and model**. Tests pass because Postgres coerces UUID↔text implicitly; production indexes may not.
- 🟡 **MED** missing unique constraint on `(roles.organization_id, roles.name)` and `(organization_members.organization_id, organization_members.user_id)`.

---

### backend/alembic/versions/7a5e08bb10ae_llm_tables.py
**Purpose:** LLM providers/secrets/agent mappings.
**Reviewed lines:** 60.

#### Issues
- 🟡 **MED** missing unique constraint on `(llm_agent_mappings.organization_id, agent_type)`.
- 🟡 **MED** line 39: `rotated_at` is `String(50)` — should be DateTime.
- 🟡 **MED** lines 36, 48: FKs to `llm_providers.id` have no `ondelete` — orphan secrets / mappings on provider delete (mitigated by ORM cascade on the relationship).

---

### backend/alembic/versions/b2c3d4e5f6a7_project_tables.py
**Purpose:** Project, subproject, requirement, connections, schemas/tables/columns.
**Reviewed lines:** 110.

#### Issues
- 🟠 **HIGH** lines 85, 95, 96: `row_count = String(20)`, `nullable = String(10)`, `ordinal_position = String(10)` — wrong types. Fixed in migration `a1b2c3d4e5f6_proper_column_types.py` (good — but the original miss reveals review/QA gap).
- 🟡 **MED** no FK on `source_connections.organization_id` → `organizations.id`.
- 🟡 **MED** subproject/requirement FK to projects has no `ondelete`.

---

### backend/alembic/versions/c3d4e5f6a7b8_agent_tables.py
**Purpose:** Agent tasks + outputs + prompt templates/versions.
**Reviewed lines:** 85.

#### Issues
- 🟠 **HIGH** lines 60-62: `started_at / finished_at / token_usage` as `String(50)` — still un-corrected by `a1b2c3d4e5f6`. Future migration needed.

---

### backend/alembic/versions/d4e5f6a7b8c9_artifact_tables.py
**Purpose:** Artifact + versions + dependency/lineage + reviews + approvals.
**Reviewed lines:** 93.

#### Issues
- 🟠 **HIGH** lines 32, 41: `version_number = String(20)` (lexicographic sort bug). `approved_at = String(50)` (timestamp as string).
- 🟡 **MED** no unique constraint on `(code_artifact_versions.artifact_id, version_number)`.

---

### backend/alembic/versions/e5f6a7b8c9d0_val_audit_health_tables.py
**Purpose:** validation_*, recon_*, audit_logs, system_health_checks.
**Reviewed lines:** 40.

#### Issues
- 🟠 **HIGH** lines 16-34: the migration is a clever DRY meta-loop but obscures the actual schema. Reading it requires mentally compiling the for-loop. Worse, lines 30-34 build the column via `sa.Column(c[0], sa.Text if c[0] in (...) else sa.String(255), nullable=not c[1])` — the field's nullability flag is `c[1]` interpreted as `is_indexed?` boolean. Confusing API; a casual reader can mis-edit.
- 🟠 **HIGH** lines 18-19: `validation_runs.started_at` declared as `String(255)` here, later corrected to `DateTime` in `a1b2c3d4e5f6`. Drop-and-recreate would be cleaner than alter; check migration history doesn't have data loss risk for shipped envs.
- 🟡 **MED** `audit_logs` has no `entry_hash` here — added later in `c4d5e6f7a8b9_password_reset_audit_hash.py`.
- 🟡 **MED** `audit_logs.actor_id` is `String(255)` — too wide for a UUID.

---

### backend/alembic/versions/f6a7b8c9d0e1_workflow_persistence_tables.py
**Purpose:** workflow_runs + workflow_steps.
**Reviewed lines:** 50.

#### Issues
- 🟠 **HIGH** line 33: `step_order = String(10)` — wrong; corrected later.
- 🟠 **HIGH** lines 41-42: `started_at / completed_at = String(50)` — wrong; corrected later.
- 🟡 **MED** line 36: `parsed_output_json = sa.Text` here; model uses `JSONB`. Type mismatch — Postgres will store JSON inside a TEXT column rather than as JSONB, breaking the GIN-index assumption.

---

### backend/alembic/versions/b2c3d4e5f6a8_composite_indexes.py
**Purpose:** Composite indexes on high-traffic tables.
**Reviewed lines:** 23.

No findings — clean migration. Good practice.

---

### backend/alembic/versions/c4d5e6f7a8b9_password_reset_audit_hash.py
**Purpose:** password_reset_tokens table + audit_logs.entry_hash.
**Reviewed lines:** 37.

#### Issues
- 🟡 **MED** line 30: `entry_hash` added as nullable. Should be NOT NULL after backfill — no backfill data migration is included.

---

### backend/alembic/versions/d5e6f7a8b9c0_org_dek_table.py
**Purpose:** org_data_encryption_keys table.
**Reviewed lines:** 34.

No findings.

---

### backend/alembic/versions/e6f7a8b9c0d1_invitations_table.py
**Purpose:** org_invitations.
**Reviewed lines:** 40.

#### Issues
- 🟡 **MED** lines 22-23: `invited_by_user_id` FK has no `ondelete` — if the inviter is deleted, the invitation row stays with a dangling FK; with default `NO ACTION` the user delete fails. Pick a policy (SET NULL?).

---

### backend/alembic/versions/f7a8b9c0d1e2_webhooks_table.py
**Purpose:** webhook_endpoints + webhook_deliveries.
**Reviewed lines:** 51.

#### Issues
- 🟡 **MED** lines 33-34: no FK constraint between `webhook_deliveries.endpoint_id` and `webhook_endpoints.id`. Orphans possible.

---

### backend/alembic/versions/a1b2c3d4e5f6_proper_column_types.py
**Purpose:** Fixup migration for H-6 (String→proper types) and H-16 (add migration_type).
**Reviewed lines:** 103.

#### Issues
- 🟠 **HIGH** lines 73-80: `nullable` column conversion uses `CASE WHEN nullable = 'YES' OR nullable = 'true' THEN true ELSE false END` — anything else becomes false. Existing rows with `null` value also become false (`columns.nullable` shouldn't have a "false" semantic by default). Acceptable if all rows were "YES"; verify.
- 🟡 **MED** missed columns: `agents.token_usage / started_at / finished_at`, `artifact_approvals.approved_at`, `code_artifact_versions.approved_at`, `llm_provider_secrets.rotated_at`. Schedule a follow-up.
- 🟡 **MED** the `postgresql_using` clauses make this migration **Postgres-only** — runs against SQLite/MySQL fail. OK for the project (Postgres is the only supported prod DB) but document.

---

### backend/alembic/versions/g8h9i0j1k2l3_connection_encrypted_config.py
**Purpose:** Add `encrypted_config` + `config_masked` to source/target_connections.
**Reviewed lines:** 37.

No findings — clean batch_alter_table usage.

---

### backend/alembic/versions/h9i0j1k2l3m4_user_preferences.py
**Purpose:** Add `users.preferences` (JSON).
**Reviewed lines:** 28.

No findings.

---

### backend/alembic/versions/i0j1k2l3m4n5_llm_provider_extra_config.py
**Purpose:** Add `llm_providers.extra_config` (JSON).
**Reviewed lines:** 33.

#### Issues
- 🟡 **MED** docstring says Bedrock can store `aws_secret_access_key` here — but this column is **plaintext JSON, not encrypted**. Document that operators should use IAM-role flows in production and treat this field as for non-secret config only.

---

### backend/alembic/versions/j1k2l3m4n5o6_sprint_management_tables.py
**Purpose:** Eight Sprint Management tables.
**Reviewed lines:** 185.

#### Issues
- 🟡 **MED** line 35: no unique constraint on `(sprints.project_id, sprints.index)`.
- 🟡 **MED** line 167: `sprint_agent_executions.task_id` is `String(36)` with no FK (task id is logical, may reference sprint_tasks). If it's meant to be an FK, declare it; otherwise note "informational" in a comment.

---

### backend/alembic/versions/k2l3m4n5o6p7_sprint_task_history.py
**Purpose:** sprint_task_history (append-only burndown source).
**Reviewed lines:** 43.

No findings — composite index `(sprint_id, created_at)` correctly aligns with the burndown query's filter.

---

### backend/Dockerfile
**Purpose:** Multi-stage build for the API container.
**Reviewed lines:** 40.

#### Issues
- 🟡 **MED** line 9-15: `pip install --no-cache-dir --prefix=/install` builds wheels at install time. No `wheels` build stage — image bloat from compilers (psycopg2-binary doesn't need them, but pyodbc does on slim images).
- 🟡 **MED** line 33: `USER 1000` — user added as `helix:1000`. Good. But the storage volume (`./data/artifacts`) mounted from compose may not be owned by 1000 — startup fails to write artifacts.
- 🟡 **MED** line 39: `CMD alembic upgrade head && uvicorn ...` — run migrations on container start means multiple replicas race to migrate. For HA deployments use a separate migration init container.
- 🔵 **LOW** line 35: HEALTHCHECK uses `urllib.request.urlopen` — fine, but it does not parse the response; a 200 with `{"status":"degraded"}` would be considered healthy.

---

### backend/requirements.txt + requirements.lock
**Purpose:** Pinned dependencies.
**Reviewed lines:** 37.

#### Issues
- 🟡 **MED** `python-jose[cryptography]` — `python-jose` has had multiple CVEs (algorithm confusion). Consider migrating to `pyjwt` or `jwcrypto`.
- 🟡 **MED** `passlib[bcrypt]>=1.7.0` is listed but the code imports `bcrypt` directly. Either drop passlib or use it consistently (passlib provides better algorithm rotation primitives).
- 🟡 **MED** `boto3>=1.34.0` — large dependency loaded even when S3 / Bedrock unused. Consider extras-style optional install (`pip install helix[aws]`).

---

### backend/tests/conftest.py
**Purpose:** Shared test fixtures.
**Reviewed lines:** 52.

#### Issues
- 🟠 **HIGH** line 16: `TEST_DATABASE_URL = "postgresql://helix:helix_password@localhost:5432/helix_test"` — tests require a running Postgres at a hard-coded URL. CI without Postgres breaks. Honor an env var.
- 🟡 **MED** lines 22-30: drop_all + create_all per test = expensive and racy if any other test connects via the app's own engine instead of `db_session`. Use transactions + rollback for isolation.

---

### backend/tests (all tests files)
**Purpose:** Pytest suite — auth, audit chain, connectors, encryption, agent workflows, projects, artifacts, llm, password reset, stored connections, agent mapping bulk, connectors extended.
**Files with tests:** 16; **files without coverage:** many (see below).

#### Coverage gaps
- No tests for: `sprints.py` (333 LOC, complex SSE + burndown logic), `webhooks.py`, `invitations.py`, `superadmin.py`, `users.py`, `system.py`, `usage.py`, `encryption.py`, `validation_service.py`, `recon_service.py`, `workflow_service.py` (only via test_agent_workflows.py partial), `email_service.py`. The audit chain is well-covered (`test_audit_chain.py`).
- No SSRF guard tests (would be valuable).
- No tests for rate limiting (because it's disabled in non-production — see rate_limiting.py finding).
- No tests for envelope encryption rotation cycle.

#### Improvements
- Add `pytest-cov` to `requirements.txt` for coverage reporting.
- Extract a `_admin_token` fixture so every test doesn't open with the 6-line `_make_admin` boilerplate.

---

### backend/app/__init__.py, app/api/__init__.py, app/services/__init__.py, app/db/__init__.py, app/auth/__init__.py, app/core/__init__.py, app/storage/__init__.py
**Purpose:** Empty package markers.

No findings.

---

## 3. Cross-cutting findings

### 3.1 Duplicated org-resolution helpers
Three near-identical helpers exist:
- `app/auth/dependencies.py::resolve_active_org_id` (canonical).
- `app/api/llm_providers.py::_org` (lines 28-30) — duplicates logic, **omits the `status='active'` filter**.
- `app/api/projects.py::_org_id` (lines 35-36) — also omits active check.
- `app/api/webhooks.py::_resolve_org_id` correctly delegates.

**Fix:** delete the duplicates; everything imports from `resolve_active_org_id`. Suspended members currently retain LLM-provider + project-listing access via these routers.

### 3.2 Inconsistent audit coverage
Audit calls exist for: projects (most mutations), LLM providers, connectors, invitations, webhooks, agent workflows, artifacts (upload only). **Missing audit on:**
- `superadmin.py` (org suspend, impersonation, *all* of it).
- `encryption.py::rotate_org_dek` (highest-value rotation event).
- `validation.py::create_rule`.
- `sprints.py::api_patch_task`, `api_create_task`.
- `auth.py::login` (success only is logged; **failed logins are not audited**).
- All schema/table/column metadata mutations.

### 3.3 BackgroundTasks + request-scoped DB session
Two endpoints schedule background tasks that try to write to the request-scoped session **after the response is sent**:
- `validation.py::start_validation` → `execute_validation_run(db, ...)` (background).
- Anywhere else? Grep shows no others, but the pattern is dangerous. Always open `SessionLocal()` inside the background task body.

### 3.4 Async-but-sync database calls
Every connector implementation declares `async def` methods whose body uses **sync SQLAlchemy `engine.connect()`**. Combined with the bare-thread executor running every async route, you get:
- Connector calls block the event loop.
- `connectors.py` + `validation.py` + `recon_service.py` all await these — entire SSE streams stall when one connector probe hangs.

**Fix:** wrap sync DB calls in `asyncio.to_thread(...)` or switch to async dialect for SQL connectors.

### 3.5 Lexicographic version sorting
`code_artifact_versions.version_number` is `String(20)` and is sorted `.desc()` in three places (artifact_version_service, code_reviews). `"10" < "2"` lexicographically — the "latest" version is wrong as soon as version count exceeds 9.

### 3.6 SQL injection via identifier interpolation
Multiple connectors use f-strings to splice schema/table names into SQL (`COUNT(*) FROM "{schema}"."{table}"`). All call `validate_identifier(...)` first, but the safety property is implicit: an accidental refactor that skips validation produces injection. Replace with SQLAlchemy's `quoted_name` / SQL-construct API.

### 3.7 SSRF guard incomplete
`app/api/connectors.py` validates connector test/discovery configs against private/loopback IPs, but `webhooks.py`, `recon_service.py`, and `validation_service.py` all dispatch to the same connector network paths **without** the guard. Webhook URLs are user-supplied and freely target metadata endpoints. Apply the guard at the network-egress site (`webhook_service.deliver_webhook`, `connector_service.test_connection`, etc.) rather than at the API boundary.

### 3.8 No rate limiting in dev/test
`rate_limiting.py` disables the limiter outside production. Combined with the absence of integration tests that exercise limiter behaviour, rate-limit bugs ship undetected. Either run a separate test profile with rate limiting enabled, or add `RATE_LIMIT_ENABLED` to config.

### 3.9 Encryption-key derivation footgun
`secret_service._get_fernet` derives a Fernet key from `settings.ENCRYPTION_KEY` via `hashlib.sha256`. Rotating `ENCRYPTION_KEY` invalidates **every** existing ciphertext silently — there's no `key_version` byte in the wire format. The per-org DEK path exists to mitigate this but isn't used by `secret_service` (only the new `envelope_encryption_service`). Path (a) callers (LLM keys, connection configs, webhook secrets) are locked into the master key forever.

### 3.10 RBAC permission reuse
`webhooks.py` and `sprints.py::api_seed_sprints` both check `admin:llm:read / write` for non-LLM operations. The `SYSTEM_PERMISSIONS` list lacks `admin:webhooks:*`, `admin:sprints:*`, `admin:audit:write`. Define them and update endpoints.

### 3.11 Pydantic response_model leakage
`UserResponse.is_super_admin: bool` is returned via `GET /auth/me`. Frontend can rely on this for UI branching but it's also a privilege-disclosure to anyone with a JWT. Acceptable for self-introspection; do NOT include it in responses listing other users.

### 3.12 Mixed UUID + String(36) primary keys
Identity tables (`users`, `orgs`, `roles`, `permissions`, `organization_members`) use Postgres `UUID`; everything else uses `String(36)`. Cross-table FKs work but indexes may not be optimal, and the inconsistency complicates ORM hydration. Pick one.

### 3.13 Pagination done in Python
`api/projects.py::api_list_projects`, `api/artifacts.py::api_list_artifacts`, etc., fetch all rows then slice. Push `limit`/`offset` into the SQL query.

### 3.14 N+1 queries
`api/superadmin.py::list_all_orgs` runs `COUNT(*)` per org. `services/llm_provider_service._to_response` decrypts API key per provider in `list_providers`. Both fixable with single query + pre-computed mask.

### 3.15 Hardcoded defaults that ship to prod
Many defaults are dev-friendly but dangerous if left unchanged: `JWT_SECRET_KEY=change_me`, `ENCRYPTION_KEY=change_me_32_byte_key`, `FRONTEND_URL=http://localhost:3000`, `EMAIL_FROM=noreply@helix-migration.app`. The `model_post_init` guard only catches `APP_ENV=production`. Add a "first-boot self-check" endpoint that lists insecure defaults regardless of env.

---

## 4. Severity summary

| Severity | Count |
|---|---|
| CRITICAL | 3 |
| HIGH | 41 |
| MED | 95+ |
| LOW | 25+ |

(Counts are approximate — the per-file tables are authoritative.)

---

## 5. Top 10 prioritized fixes

1. **`backend/app/services/llm_provider_service.py:91`** — `rotated_at=str(uuid.uuid4())` writes a UUID into a timestamp field. Replace with `datetime.now(timezone.utc).isoformat()`.
2. **`backend/connectors/sqlserver/connector.py:44`** — `trust_cert = "no" if cfg.get("trust_server_certificate", False) else "no"` — both branches are `"no"`. Fix the typo so users with self-signed certs can connect.
3. **`backend/app/core/config.py:16,28,30`** — replace `"change_me"` JWT/encryption defaults with `secrets.token_hex(32)` factories; fail closed when defaults ship outside `APP_ENV=production`.
4. **`backend/app/api/superadmin.py:73-92`** — embed `imp_by` claim in the impersonation JWT, propagate to `write_audit`, and audit every super-admin action (org suspend, status change).
5. **`backend/app/api/audit.py:30 + 43-63`** — separate `AUDIT_HMAC_KEY` from `JWT_SECRET_KEY`; serialize audit writes per-org with an advisory lock to prevent chain forks under concurrency.
6. **`backend/app/api/webhooks.py`** — add SSRF guard (`_enforce_host_allowlist`) on webhook URL registration + delivery. Today an admin can point a webhook at AWS IMDS.
7. **`backend/app/services/validation_service.py:59-138` + `recon_service.py:39-50`** — open `SessionLocal()` inside background tasks (request-scoped session is closed); apply SSRF guard on connector configs that flow through these paths.
8. **`backend/app/services/workflow_service.py:83-89`** — wrap `helix.run()` in `await asyncio.to_thread(...)` so the local-fallback path doesn't block the event loop.
9. **All connectors (`connectors/postgres/connector.py` and siblings)** — declared `async` but body is sync SQLAlchemy. Wrap with `asyncio.to_thread` or switch to async drivers.
10. **`backend/app/services/secret_service.py:14` + `app/services/llm_provider_service.py:36`** — handle empty `api_key` (Bedrock/Vertex IAM auth) without raising; also pre-compute `api_key_masked` at write time instead of decrypting on every list.

Bonus (#11): **`backend/app/models/artifacts.py:27` + `backend/app/services/artifact_version_service.py:65`** — fix lexicographic version sort by switching `version_number` to Integer.

---

## 6. Architecture suggestions

### 6.1 Extract org/user/auth into a single dependency tuple
Every authenticated route resolves `user_id`, `org_id`, and often `user` (full row). Today it's done via two-to-three separate `Depends(...)` per route. Introduce:

```python
@dataclass
class AuthContext:
    user_id: str
    org_id: str
    user: User
    role: Role
    request_id: str
```

…and a single `Depends(get_auth_context)` returning it. Eliminates the duplicated `_org(db, uid)` helpers in three routers and forces a single org-resolution path.

### 6.2 Push pagination into queries; use keyset pagination
Replace `rows[offset:offset+limit]` with `query.limit(limit).offset(offset)`. For deep pages (admin audit views, project lists), switch to keyset pagination (`WHERE created_at < :before LIMIT :limit`) so a 30-day audit export doesn't OFFSET-scan 1M rows.

### 6.3 SSE → real pubsub
Both SSE generators (`agent_workflows::stream_workflow_progress`, `sprints::api_executions_stream`) poll the DB at 1-2s intervals. Wire to Redis pubsub (`channel = workflow:{id}`, `channel = exec:{project_id}`) and have the workflow / agent path publish on completion. Drops DB load to zero between events and removes the artificial 2-minute / 5-minute caps.

### 6.4 Unify the two encryption paths
The codebase ships both `secret_service.py` (deterministic-key Fernet) and `envelope_encryption_service.py` (per-org KEK/DEK), but only the first is used by production callers (LLM keys, connection configs, webhook secrets). Migrate all `encrypt_value(...)` callers to `encrypt_for_org(db, org_id, ...)`. Side benefits:
- Per-org key rotation actually invalidates only that org's ciphertexts.
- Compromise of one org's DEK doesn't bleed across tenants.
- The `POST /admin/org/rotate-dek` endpoint becomes meaningful.

### 6.5 Move connectors to fully async
The `connectors/*` package uses sync SQLAlchemy under `async def`. Either:
- Adopt `asyncpg` + `aiomysql` + `aioodbc` and rewrite per-connector,
- Or keep sync and wrap call-sites in `asyncio.to_thread`.

The latter is less work; pick one and stop pretending it's async.

### 6.6 Centralise enum strings → proper enums
Status / health / priority / risk_level / connector_type are scattered as `String(N)` with inline comments listing valid values. Lift to `Enum` types (Python + SQL `CHECK` constraints) — Pydantic + SQLAlchemy both support enum columns natively.

### 6.7 Make audit-log writes append-only at the DB level
Audit is meant to be tamper-evident; right now any DB-level UPDATE silently breaks the chain. Add an `INSERT-only` ROW LEVEL SECURITY policy + revoke UPDATE/DELETE on `audit_logs` from the API role. The `entry_hash` mismatch then becomes a *detection* mechanism on the rare cases that bypass RLS.

### 6.8 Replace `python-jose` with `pyjwt`
python-jose is barely maintained and has had multiple CVEs (alg-none, alg-switch). PyJWT (or `jwcrypto` for JWS/JWE) is a drop-in replacement with active security review.

### 6.9 Make migrations idempotent / safe-for-rollout
Several migrations rely on Postgres-only constructs (`postgresql_using`, batch_alter_table on JSON). Document the supported DB matrix explicitly (Postgres ≥14 only). Add a Makefile target `make migrate-check` that runs `alembic upgrade head` then `alembic downgrade -1` then `alembic upgrade head` against a scratch DB.

### 6.10 Service-level transaction boundaries
Routers do `db.commit()` and services do `db.commit()` and audit-write does `db.commit()` — there's no single transaction boundary per request. Refactor to a "unit of work" pattern: the service returns its desired state, the router commits once at the end, audit hooks fire post-commit. Otherwise a half-completed mutation can leave audit + entity in inconsistent states.
