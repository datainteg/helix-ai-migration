# Documentation Audit — Wave-1 + Wave-2 Currency Report

**Audit Date:** 2026-05-26  
**Scope:** Six root-level docs + `docs/DR.md`, `docs/MIGRATION_NOTES.md`, `docs/ROADMAP.md`  
**Baseline:** Latest commits include 44 route metadata additions (A11Y-59), SEC-010/011, DI-C1 (DEK rotation), v0.2.0 SDK/CLI, pagination envelope, new endpoints (replay, pair-review, rollback), knowledge/marketplace, schema-drift, compliance PDF, cutover state machine.

---

## Per-Document Audit

### 1. `README.md` — ❌ MISLEADING on SDK/CLI, ⚠️ Missing key features

**Current state vs reality:**
- README is pre-v1.0 ✓ (line 195) but misses v0.2.0 SDK/CLI and their breaking changes
- Claims stack support (line 39-44) but frontend modal a11y refactored in wave-2, not mentioned
- No "install in 1 command" section (quick-start is 5-step, not 1-click)

**Specific edits needed:**
- **Line 46–66 (Quick start):** Add section header "Quick start (≈ 1 minute)" and insert one-liner:
  ```bash
  ./setup.sh && open http://localhost:3000/setup/first-admin
  ```
  Keep the 5-step manual as "Detailed steps" below.

- **After line 68 (Full deployment guide):** Add new "SDK & CLI" section:
  ```markdown
  ## SDK & CLI (v0.2.0)
  
  - **Python SDK:** `pip install helix-sdk`; `.paginated()` method for envelope-aware list pagination
  - **TypeScript SDK:** npm-installable with types; same `.paginated()` surface
  - **CLI:** `pip install helix-cli`; login, projects, workflows, templates, cost, cutover commands
  - **Breaking change:** All list endpoints now return `{items, total, limit, offset}` envelope. SDKs unwrap transparently via `.list()` (back-compat bare array) and `.paginated()` (new).
  ```

- **After line 92 (13-node pipeline table):** Add note after row 12:
  ```markdown
  | 13 | paige_docs | Paige | bmad-document-project | 5 — Docs |
  ```
  Insert: "New in wave-2: endpoints for replay (`POST /workflows/{id}/replay`), pair-review (`POST /artifacts/{id}/pair-review`), and rollback (`POST /artifacts/{id}/rollback-generate`)."

- **After line 140 (LLM provider support):** Add subsection "Wave-2 additions":
  ```markdown
  ### New Features (Wave-2)
  - **Marketplace:** 7 built-in plugins + custom registry
  - **Knowledge base:** RAG document upload + keyword search (vector embeddings pending)
  - **Schema drift watcher:** Real-time drift detection between snapshots
  - **Compliance PDF:** Audit chain + validation + recon + cutover artifacts as one PDF per project
  - **Cutover state machine:** bulk → tail → freeze → diff → flip → done / rolled_back
  - **All routes have a11y metadata:** 44 Next.js pages + metadata.title on every route (A11Y-59)
  ```

- **Line 195 (Status):** Change `Pre-1.0` to `v0.2.0 (Core ✓, SDK/CLI + FE redesign ongoing)`.

---

### 2. `DEPLOY.md` — ⚠️ Missing wave-2 migration notes, silent on DATABASE_URL gotcha

**Current state vs reality:**
- Covers setup + day-2 ops ✓
- Does NOT mention wave-2 migrations `2af2b45b4051` (DEK partial-unique) or `q8r9s0t1u2v3` (encrypt extra_config)
- Silent on asyncpg vs psycopg2 driver split (real gotcha for operators)
- No mention of new alembic migrations (28 total now, was ~20 in wave-1)

**Specific edits needed:**
- **After line 150 (full list comment):** Insert new section:
  ```markdown
  ### Critical migration notes (wave-2)
  
  If upgrading from wave-1:
  
  1. **Migration `2af2b45b4051`** — relaxes `org_data_encryption_keys.organization_id` from full UNIQUE to partial UNIQUE on `(organization_id) WHERE is_active=true`. This allows DEK rotation to succeed. Safe to rerun.
  2. **Migration `q8r9s0t1u2v3`** — encrypts plaintext secrets in `llm_providers.extra_config` (Bedrock `aws_secret_access_key`, Vertex `service_account_json`, Azure `client_secret` fields). Idempotent; skips already-encrypted rows.
  3. **Alembic version management:** `alembic upgrade head` applies all pending migrations atomically. No downtime required on empty or populated DBs.
  ```

- **After line 78 (docker compose up -d):** Insert driver clarification:
  ```markdown
  #### DATABASE_URL driver gotcha
  
  The async SQLAlchemy engine converts `postgresql://` → `postgresql+asyncpg://` for async contexts (background tasks, SSE streams). Sync paths (alembic, sync DB work wrapped in `asyncio.to_thread`) continue using psycopg2. **Do not manually set DATABASE_URL to `postgresql+asyncpg://`** — the application rewrites it. See `backend/app/db/session.py:8-10` for the rewrite logic.
  ```

- **After line 202 (Apply migrations):** Add subsection:
  ```markdown
  #### Post-upgrade verification
  
  After `alembic upgrade head`, confirm:
  1. No orphaned workflows in `awaiting_approval` — approve or reject them first.
  2. `SELECT COUNT(DISTINCT organization_id) FROM org_data_encryption_keys WHERE is_active=true;` returns the number of organizations.
  3. `SELECT COUNT(*) FROM llm_provider_secrets WHERE encrypted_api_key LIKE '%encrypted%';` should be > 0 if you have LLM providers (post-q8r9s0t1u2v3).
  ```

---

### 3. `docs/DR.md` — ✅ Current, minor clarification on DEK state

**Current state vs reality:**
- Backup + restore scripts are wave-2-aware ✓
- RPO/RTO targets are sound ✓
- Missing one detail: `rotate_dek` state during backup

**Specific edits needed:**
- **After line 16 (backup volumes):** Add note:
  ```markdown
  ⚠️ **If running `POST /admin/org/rotate-dek` mid-backup:** The backup is still safe. The rotation is transactional; either the old or new DEK is active, never both. Restore will see only the final state.
  ```

---

### 4. `docs/MIGRATION_NOTES.md` — ✅ Comprehensive, now 1:1 with wave-2 code

**Current state vs reality:**
- Covers ENCRYPTION_KEY derivation change ✓
- Covers per-org DEK rotation + operator runbook ✓
- Covers UUID → String(36) ✓
- Covers workflow_steps JSONB migration ✓
- Covers cost-service batching ✓
- NEW: Also covers Fernet legacy fallback + extra_config encryption (q8r9s0t1u2v3)

**Specific edits needed:**
- **NONE.** This file is fully synced. Wave-2 changes are all described.

---

### 5. `docs/ROADMAP.md` — ✅ Shipped features inventory accurate

**Current state vs reality:**
- "Shipped (12 commits)" section (line 8) lists v0.2.0 SDK + CLI ✓
- Mentions pagination envelope ✓
- Mentions compliance PDF, cutover state machine, schema drift, knowledge, marketplace ✓
- Mentions `/workflows/{id}/replay` endpoint ✓
- Mentions `POST /artifacts/{id}/pair-review` endpoint ✓
- Mentions A11Y-59 (44 routes with metadata.title) ✓

**Specific edits needed:**
- **NONE.** This file is fully accurate.

---

### 6. `SECURITY.md` — ⚠️ Missing wave-2 encryption additions

**Current state vs reality:**
- JWT auth, RBAC, audit logging ✓
- LLM API key encryption ✓
- Silent on wave-2: extra_config field encryption (SEC-010), per-org DEK rotation (DI-C1), artifact frontmatter scrubbing (SEC-011)

**Specific edits needed:**
- **After line 31 (API key encryption):** Insert:
  ```markdown
  | **Secret config encryption (wave-2)** | LLM provider `extra_config` fields (Bedrock, Vertex, Azure creds) encrypted at rest using org DEK; decrypted only on outbound call (SEC-010) |
  | **Per-org data encryption key (DEK)** | Rotation via `POST /admin/org/rotate-dek` with zero-downtime re-wrap; historical keys retained for legacy-decrypt walk (DI-C1) |
  | **Artifact frontmatter scrubbing** | Sensitive keys stripped from BMAD artifact metadata before storage; compliance PDF redacts same (SEC-011) |
  ```

---

### 7. `docs/deployment/INSTALLATION.md` — ❌ STALE, conflicts with root DEPLOY.md

**Current state vs reality:**
- Says frontend is on port 8080 (actually 3000) — **WRONG**
- Says backend is on 8000 ✓
- References `.env.example` → `.env` (outdated; now uses `setup.sh`)
- Silent on v0.2.0 SDK/CLI install
- No mention of pagination envelope or new endpoints

**Specific edits needed:**
- **Line 1:** Change title to `# Installation Guide — LEGACY (See DEPLOY.md for current flow)`
- **Lines 23–28 (Expected URLs):** Fix:
  ```
  Frontend:    http://localhost:3000
  Backend API: http://localhost:8000
  Temporal UI: http://localhost:8233
  ```
- **After line 20 (compose up):** Add:
  ```markdown
  ⚠️ **DEPRECATED:** Use `./setup.sh` (Linux/macOS) or `.\setup.ps1` (Windows) instead. This guide is archived for reference only.
  ```
- **At end (before Troubleshooting):** Add:
  ```markdown
  ## SDK Installation
  
  After the backend is live:
  
  ```bash
  pip install helix-sdk      # Python; includes `.paginated()` method for pagination envelope
  pip install helix-cli      # CLI tool; login, projects, workflows, templates, cost
  npm install @helix/sdk     # TypeScript; types included
  ```
  ```

---

## Documentation Drift Verdict

| Document | Status | Severity | Summary |
|----------|--------|----------|---------|
| `README.md` | ❌ MISLEADING | **HIGH** | Missing SDK v0.2.0, CLI, 1-click install, new endpoints (replay, pair-review), marketplace, knowledge, A11Y metadata. "Pre-1.0" should clarify "v0.2.0 (API + infrastructure stable; SDK/CLI + FE in flight)". |
| `DEPLOY.md` | ⚠️ STALE | **MEDIUM** | Silent on wave-2 migrations (DEK partial-unique, extra_config encryption). No mention of DATABASE_URL asyncpg→psycopg2 driver split (operator gotcha). Missing post-upgrade verification steps. |
| `docs/DR.md` | ✅ CURRENT | — | Backup/restore scripts correctly reflect wave-2 DEK state. No edits needed. |
| `docs/MIGRATION_NOTES.md` | ✅ CURRENT | — | Comprehensive coverage of ENCRYPTION_KEY, DEK rotation, UUID migration, JSONB migration, legacy Fernet fallback, extra_config encryption. Matches code exactly. |
| `docs/ROADMAP.md` | ✅ CURRENT | — | "Shipped" section accurately lists all v0.2.0 + wave-2 features (SDK, CLI, pagination, endpoints, marketplace, knowledge, cutover, compliance, A11Y). Pending/next-up picks sound. |
| `SECURITY.md` | ⚠️ STALE | **MEDIUM** | Missing wave-2 additions: extra_config field encryption (SEC-010), per-org DEK rotation (DI-C1), artifact frontmatter scrubbing (SEC-011). |
| `docs/deployment/INSTALLATION.md` | ❌ OBSOLETE | **HIGH** | Port numbers wrong (says 8080 for frontend, actually 3000). References `.env.example` flow (now `setup.sh`). No SDK/CLI/pagination docs. Archive this file and cross-reference `DEPLOY.md`. |

---

## Summary

**Overall verdict:** ⚠️ **STALE across 3 of 7 docs**, with 2 CRITICAL gaps (README, INSTALLATION.md).

**Recommend:**
1. **README.md:** Add SDK v0.2.0 + CLI section + 1-click install banner + new wave-2 features (knowledge, marketplace, compliance, A11Y) + replay/pair-review endpoints.
2. **DEPLOY.md:** Insert wave-2 migration guide (2af2b45b4051, q8r9s0t1u2v3) + DATABASE_URL driver clarification + post-upgrade verification.
3. **SECURITY.md:** Add row for extra_config + DEK rotation + artifact scrubbing (SEC-010, DI-C1, SEC-011).
4. **INSTALLATION.md:** Deprecate + cross-reference DEPLOY.md. Fix port numbers. Add SDK install snippet.
5. **MIGRATION_NOTES.md, DR.md, ROADMAP.md:** No changes — all synced.

**Ship readiness:** Docs are impedance match for **qualified operators** who have read ROADMAP + MIGRATION_NOTES. Generic new users will miss SDK/CLI and be confused by missing 1-click install mention in README. Suggest light marketing copy in README emphasizing the new v0.2.0 SDK surface + "self-hosted in 1 command" pitch.
