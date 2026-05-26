# WAVE-3 FIX SUMMARY — Deploy-Fix Sprint Aggregator Report

**Generated:** 2026-05-26 17:22 IST  
**Aggregator:** WAVE-3 DEPLOY-FIX AGGREGATOR (read-only)  
**Method:** `git log --oneline --grep` polling every 90 s; diffs verified via `git show --stat`  
**Threshold:** 7/10 agents committed → met at check-4 (≈ 6 minutes elapsed)  
**Final count:** 8/10 agents committed; F2 (compose) and F9 (deps/lockfile) did NOT commit within the 30-minute window

---

## 1. Per-Fixer Table

| Agent | Scope pattern | Commits | SHAs | Blocker addressed |
|-------|--------------|---------|------|-------------------|
| **F1** | `fix(setup):` | 5 | eed0cadf, 8134f2b8, d29037bc, 21748dd6, 170c2512 | B-1 (partial), B-8, B-10 |
| **F2** | `fix(compose):` | 0 | — | B-2 (NOT closed), B-9 |
| **F3** | `fix(secrets):` | 3 | 321feca0, 95644c1b, 4b264137 | B-4 |
| **F4** | `fix(docker): backend` | 1 | 6c8fddf4 | B-6 |
| **F5** | `fix(worker):` | 3 | bdb735c5, 57b19113, 1c4f1f12 | B-9 (partial), worker HIGH-set |
| **F6** | `fix(docker): frontend` | 1 | 6ba10b30 | FE quality (FE-001,004,006) |
| **F7** | `fix(security):` | 16 | 556a482c, 079b5d25, 593f054a, dd621b56, 8b6bcc3d, f433ccf3, 108e843b, e71c57e8, fac8ef86, 136d1ac9, a0eddaef, 125f56bf, 1822aff3, 719846a3, 7afa1fe8, f7f1bd24 | B-8 (re-encryption CLI), SEC-001..SEC-018 |
| **F8** | `docs:` + `feat(cli):` | 2 wave-3 | 7841c5b1, 4baa1d62 | B-10 (headless admin), B-1 doc side |
| **F9** | `fix(deps):` | 0 | — | B-7 NOT closed |
| **F10** | `fix(bmad):` | 1 | 4009a2c4 | B-5 (partial) |

> Note: F5 `bdb735c5` was titled `fix(worker)` but its actual file diff covered `docker-compose.yml`, `docker-compose.build.yml`, `docker-compose.dev.yml`, `Caddyfile`, and `.env.example` — effectively doing F2's job as a side effect. See §3 for scope-creep analysis.

---

## 2. Blocker Status (B-1 through B-10)

### B-1 — `NEXT_PUBLIC_API_URL` baked at build time, defaults to `localhost` ⚠️ PARTIAL

**Agent responsible:** F1 (setup.sh), F8 (docs)  
**Evidence:**
- `d29037bc` (setup.sh): `detect_public_ip()` function added; GCE metadata + AWS IMDSv2 fallback; writes `NEXT_PUBLIC_API_URL=http://<ip>:8000` into `.env` before the build step; `--domain` flag stamps `NEXT_PUBLIC_API_URL=https://<domain>`.
- `7841c5b1` (docs): DEPLOY.md documents the GCP one-VM section with `NEXT_PUBLIC_API_URL` handling.

**Why partial:**  
The frontend Dockerfile (`6ba10b30`, F6) does not inject `NEXT_PUBLIC_API_URL` as a `--build-arg`. The fix relies on `setup.sh` writing the value into `.env` before `docker compose build`, but the Next.js build only picks up `NEXT_PUBLIC_*` args baked at build time if they are passed via `--build-arg` or `ARG`/`ENV` in the Dockerfile. The Dockerfile does NOT have an `ARG NEXT_PUBLIC_API_URL` line. If the operator runs `docker compose build` independently (without going through `setup.sh`), they will still get a `localhost:8000` bundle.

**Risk:** Medium. Operators using `setup.sh` exclusively are protected. Docker-native operators are not.

---

### B-2 — Backend/frontend ports bound to `0.0.0.0` by default; full API surface publicly exposed ✅ CLOSED

**Agent responsible:** F5 (`bdb735c5`, scope-creep into compose territory)  
**Evidence:**  
`docker-compose.yml` now reads:
```yaml
- "${BACKEND_BIND:-127.0.0.1}:${BACKEND_HOST_PORT:-8000}:8000"
- "${FRONTEND_BIND:-127.0.0.1}:${FRONTEND_HOST_PORT:-3000}:3000"
```
Temporal UI:
```yaml
- "${TEMPORAL_UI_BIND:-127.0.0.1}:${TEMPORAL_UI_HOST_PORT:-8233}:8080"
```
All three services default to loopback. `.env.example` (`bdb735c5`) documents `BACKEND_BIND=127.0.0.1` and `FRONTEND_BIND=127.0.0.1` with an explicit comment: "Set to 0.0.0.0 only for local development without Caddy; never in production."  

Caddy service added to `docker-compose.yml` on ports 80/443; `Caddyfile` blocks `GET /metrics` with `respond 403`.

**Note:** The DEPLOY.md doc by `7841c5b1` removes the dangerous `ufw allow 8000/tcp` instruction.

---

### B-3 — No TLS anywhere in the stack ✅ CLOSED

**Agent responsible:** F5 (`bdb735c5`)  
**Evidence:**  
`Caddyfile` (77 lines) committed. Caddy 2 Alpine service added to `docker-compose.yml`:
- Auto-obtains Let's Encrypt certs on HTTPS 443 (ACME HTTP-01 challenge on 80)
- SSE paths (`/api/v1/sse/*`, `/api/v1/agent-workflows/*/stream`) get `flush_interval -1`
- `X-Forwarded-Proto https` passed upstream
- `/metrics` blocked with `respond 403`
- HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy headers set
- `HELIX_PUBLIC_DOMAIN` required env var (`:?` form; compose fails-fast if unset)

**Note:** This is real TLS, not just documentation. The Caddyfile is operative. ✅

---

### B-4 — Fernet key generation broken; backend refuses to boot ✅ CLOSED

**Agent responsible:** F3 (`321feca0`, `95644c1b`, `4b264137`)  
**Evidence:**
- `321feca0`: `generate-secrets.sh` now has `rand_fernet_key()` using `openssl rand 32 | base64 | tr '/+' '_-'` — the `=` padding is preserved. Hard-fails (exit 1) if neither `python3+cryptography` nor `openssl` is available.
- `generate-secrets.ps1` has `RandFernetKey` function that does NOT call `.TrimEnd('=')`.
- `4009a2c4` (F10): `backend/app/core/config.py` validator now checks `len(key) != 44` BEFORE `base64.urlsafe_b64decode`, removing the broken `+ "=="` padding-injection that allowed 43-char keys to pass silently.
- `95644c1b`: regression tests in `backend/tests/test_secret_generation.py` cover 43-char rejection, 44-char acceptance, and round-trip encrypt/decrypt.

**Note:** Length check + script fix + test = fully closed. ✅

---

### B-5 — BMAD artifacts written to ephemeral container layer ⚠️ PARTIAL

**Agent responsible:** F5 (`bdb735c5`, compose volume fix), F10 (`4009a2c4`, startup assertion)  
**Evidence:**
- `bdb735c5` (F5): worker's volume mount changed to `helix_artifacts:/app/_bmad-output`, aligning with `_bmad/bmm/config.yaml`'s `{project-root}/_bmad-output` path.
- `4009a2c4` (F10): `_verify_bmad_artifact_store()` at worker startup does a test write+unlink to verify the mount is writable; hard-fails in production.

**Remaining gap:**  
The **backend** artifact service still mounts `helix_artifacts:/app/data/artifacts`. This means the same volume (`helix_artifacts`) is mounted at **two different container paths**:
- Worker writes to `/app/_bmad-output/planning-artifacts/` (inside the volume)
- Backend reads from `/app/data/artifacts/` (root of the same volume)

These are different paths within the same volume. The backend's `GET /api/v1/agent-workflows/{id}/artifact-content` API reads `data/artifacts/` but BMAD artifacts are in `_bmad-output/`. The artifacts are **persisted** now (no longer ephemeral) but **still not visible to the backend API**. B-5 is half-fixed: durability restored, cross-service visibility broken.

**Risk:** HIGH. Artifact content endpoint returns 404 for all BMAD-generated artifacts.

---

### B-6 — Backend Dockerfile shell-form CMD; SIGTERM never reaches uvicorn ✅ CLOSED

**Agent responsible:** F4 (`6c8fddf4`)  
**Evidence:**  
`backend/Dockerfile` ENTRYPOINT is now:
```dockerfile
ENTRYPOINT ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-2}"]
```
`exec` makes uvicorn PID 1; SIGTERM is forwarded directly. Alembic migration removed from startup (delegated to `backend-init` one-shot service in compose). Also: bookworm base image pinned, `unixodbc libodbc2` added (prevents `ImportError` for SQL Server connector), `pytest` dev deps removed from production `requirements.txt`.

---

### B-7 — Worker lockfile generated on Python 3.13/Windows; runner is Python 3.11/Linux ❌ NOT CLOSED

**Agent responsible:** F9 (fix(deps):) — DID NOT COMMIT  
**Evidence:**  
`worker/requirements.lock` header still reads:
```
# This file is autogenerated by pip-compile with Python 3.13
```
`pywin32==311` and `pywin32-ctypes==0.2.3` are still present (Windows-only packages that fail Linux install).  
`google-cloud-aiplatform` is still absent from the lockfile.

**Risk:** CRITICAL. Worker image on GCP Linux will install pywin32 (may fail) and will use unconstrained resolution for `google-cloud-aiplatform`. ABI-tagged wheels for `grpcio`, `cffi`, `psycopg2-binary` will be CP313 builds, not CP311.

---

### B-8 — `--rotate-secrets` silently destroys encrypted credentials ✅ CLOSED

**Agent responsible:** F1 (`d29037bc`), F7 (`f7f1bd24`), F5 (compose — added backend-init)  
**Evidence:**
- `d29037bc`: `setup.sh --rotate-secrets` now requires both `--force` AND `--confirm-data-loss`; exits 2 with a warning if either flag is missing.
- `setup.ps1` (`21748dd6`) has `-RotateSecrets` requiring `-Force` AND `-ConfirmDataLoss`.
- `f7f1bd24` (F7, security): adds `backend/app/cli/rotate.py` with `rotate-keks`, `rotate-dek`, `rotate-all-deks` commands that actually re-encrypt data; dry-run by default; `--confirm` required to commit.

**Note:** The CLI rotate orchestrator is not yet wired into `setup.sh --rotate-secrets` (it just gates the call), but the data-loss scenario is blocked. ✅

---

### B-9 — Compose `mem_limit` sum exceeds 4 GB on e2-medium target ⚠️ PARTIAL

**Agent responsible:** F5 (`bdb735c5`)  
**Evidence:**  
`bdb735c5` rewrote `docker-compose.yml` with per-service `mem_limit` values. Adding them:

| Service | mem_limit |
|---------|----------|
| postgres | 700m |
| redis | 200m |
| temporal | 600m |
| temporal-ui | 100m |
| backend-init | 400m |
| backend | 800m |
| worker | 800m |
| frontend | 400m |
| caddy | 100m |
| **Total** | **4100m** |

4100 MB > 4096 MB (4 GB). The comment says "Sized for a GCP e2-medium (2 vCPU / 4 GB RAM)" but the limits sum to 4.0 GB plus OS overhead (~500 MB) plus Docker daemon. The effective ceiling is 3712 MB to leave headroom. The original blocker report specified ≤ 3712 MB OR recommend e2-standard-2 (8 GB). Neither condition is fully met. The header comment says "Bump mem_limit values if running on e2-standard-2+ (8 GB)" but doesn't recommend it as minimum.

**Risk:** LOW-MEDIUM. The OOM killer will occasionally evict the heaviest service (worker or backend) under full load on e2-medium. Still an improvement over the prior unlimited state.

---

### B-10 — No Docker installer; placeholder repo URL; first-admin UI-only ✅ CLOSED

**Agent responsible:** F1 (setup.sh bootstrap), F8 (docs + CLI)  
**Evidence:**
- `d29037bc`: `setup.sh` auto-installs Docker CE via `get.docker.com` on Ubuntu/Debian/Fedora/RHEL/Alpine/Arch; detects if user is not in `docker` group and instructs `newgrp docker`; iptables-nft detection for Ubuntu 24.
- `170c2512`: `CONTRIBUTING.md` and `DEPLOY.md` canonical repo URL `https://github.com/datainteg/helix-ai-migration.git` replaces `<your-fork>` placeholders; new `docs/INSTALL.md` with one-command `curl|bash` recipe.
- `7841c5b1` (docs): README updated with canonical URL, v0.3.0 status, one-command install section.
- `4baa1d62` (feat(cli):): `helix admin bootstrap` subcommand: `--email`, `--password`, `--org-name`, `--accept-tos`; calls `POST /api/v1/auth/first-admin`; idempotent; reads `.helix-bootstrap` sentinel written by `setup.sh`.
- `helix install` subcommand chains `setup.sh` → `admin bootstrap` for a single-command deploy.

---

## 3. Cross-Cutting Issues

### 3.1 Scope Creep: F5 (`fix(worker): bdb735c5`) Overstep

**Severity: HIGH**

F5's commit `bdb735c5` was labelled "W-003 concurrency cap + W-007 graceful shutdown" but its diff touched **5 files outside the worker boundary**:
- `docker-compose.yml` (B-2, B-3, B-5, B-9 all addressed here — F2's territory)
- `docker-compose.build.yml`
- `docker-compose.dev.yml`
- `Caddyfile` (new file — F2's territory)
- `.env.example` (F3's territory)

F2 (fix(compose):) did not commit at all — it is entirely superseded by F5's overstep. This is not a conflict (the final state is consistent), but it breaks the "one agent per concern" model, making rollback and attribution harder.

### 3.2 Scope Creep: F6 (`fix(docker): frontend 6ba10b30`) Touching `worker/main.py`

**Severity: MEDIUM**

F6's commit `6ba10b30` is titled "frontend Dockerfile — deterministic npm ci, node 20.20.2 pin" but it also modified `worker/main.py` with the concurrency/graceful-shutdown additions (`max_concurrent_activities`, `graceful_shutdown_timeout`, SIGTERM handler). This duplicates F5's intent. The later F5 commit (`bdb735c5`, timestamp 17:14:53 vs F6's 17:14:30) appears to have built on the state after F6 modified worker/main.py. No line-level conflict exists because F5 did NOT re-touch `worker/main.py` (it left it as-is after F6 wrote it).

**Consequence:** F6's commit message is misleading — the commit is not just about frontend. If F6 is reverted (e.g., for a frontend-only hotfix), the worker concurrency caps go with it.

### 3.3 Duplicate F7 Commits: Two Versions of `fix(security): sanitize artifact filenames`

**Evidence:** Both `556a482c` (2026-05-23) and `079b5d25` (older commit) have identical subjects `"fix(security): sanitize artifact filenames and prevent path traversal"`. The older one (`556a482c`) predates the wave-3 window and likely is from a prior sprint. No conflict — later commit `079b5d25` is the authoritative one.

### 3.4 Cross-Agent File: `worker/main.py` Touched by F6, F5, F10

Three agents touched `worker/main.py` in the same wave:
- `6ba10b30` (F6): added concurrency + shutdown (timestamp 17:14:30)
- `bdb735c5` (F5): touched compose/caddy/.env.example only — worker/main.py NOT in this commit's diff (contradicts F5's message which implies it added the SIGTERM handler)
- `4009a2c4` (F10): added `_verify_bmad_artifact_store()` startup check and `bmad_loader` import

**Actual commit order on `worker/main.py`:** F6 (17:14:30) → F10 (17:18:16). No merge conflict (sequential linear commits). But F5's commit message claims credit for changes that are in F6's diff — the concurrency cap and graceful-shutdown code is physically in F6.

### 3.5 Cross-Agent File: `backend/app/core/config.py` Touched by F10

F10 (`4009a2c4`) modified `backend/app/core/config.py` to add the `len(key) != 44` length guard. This is the backend/secrets concern — F3 owns the generator scripts, but F10 owns the config validator. The two agents addressed complementary halves of B-4. No conflict.

### 3.6 `helix_artifacts` Volume Mount Path Inconsistency (B-5 Partial Fix)

F5 (`bdb735c5`, compose) set worker's volume to `helix_artifacts:/app/_bmad-output`. The backend service volume was not changed and still reads `helix_artifacts:/app/data/artifacts`. Within the Docker volume's filesystem, the worker writes to `_bmad-output/` and the backend mounts the same volume but sees `data/artifacts/` as its root. Artifacts created by the worker at `/app/_bmad-output/planning-artifacts/*.md` are visible to the backend only at the path `data/artifacts/_bmad-output/...` — which the artifact API does not know about.

This was NOT raised as an active conflict between agents, but is a semantic inconsistency that B-5's fix introduced: the volume is now shared but the paths diverge.

---

## 4. Updated Pre-Deploy Checklist

| # | Blocker | Status | Notes |
|---|---------|--------|-------|
| B-1 | `NEXT_PUBLIC_API_URL` auto-detection | ⚠️ PARTIAL | setup.sh path fixed; frontend Dockerfile has no `ARG NEXT_PUBLIC_API_URL` |
| B-2 | `0.0.0.0` port bindings | ✅ CLOSED | All services default to 127.0.0.1; Caddy on 80/443 |
| B-3 | No TLS | ✅ CLOSED | Caddyfile + caddy service committed; auto-LetsEncrypt |
| B-4 | Fernet key generation broken | ✅ CLOSED | Scripts fixed, validator fixed, tests added |
| B-5 | BMAD artifacts ephemeral | ⚠️ PARTIAL | Worker volume aligned; backend reads different path |
| B-6 | Shell-form CMD swallows SIGTERM | ✅ CLOSED | exec-form ENTRYPOINT; alembic in backend-init one-shot |
| B-7 | Worker lockfile Python 3.13/Windows | ❌ NOT CLOSED | `pywin32` still in lockfile; CP313 wheels; no fix committed |
| B-8 | `--rotate-secrets` destroys credentials | ✅ CLOSED | Requires `--force --confirm-data-loss`; re-encryption CLI added |
| B-9 | mem_limits exceed 4 GB | ⚠️ PARTIAL | Total 4100m; still over headroom on e2-medium |
| B-10 | No Docker installer; placeholder URL | ✅ CLOSED | Docker bootstrap in setup.sh; canonical URL; helix admin bootstrap |

**Summary: 5 CLOSED ✅ / 3 PARTIAL ⚠️ / 2 NOT CLOSED ❌**

### Outstanding Work Before GCP Production Deploy

**Must fix (remaining blockers):**

1. **B-7 (P0):** Regenerate `worker/requirements.lock` and `backend/requirements.lock` inside a `python:3.11-slim` Docker container. Remove `pywin32==311` and `pywin32-ctypes==0.2.3`. Add `google-cloud-aiplatform` to the lockfile. ETA: 30 minutes with `scripts/lock-requirements.sh` (if it exists) or a manual `pip-compile` run.

2. **B-5 (P1):** Align backend artifact read path with worker write path. Either:
   - Change backend volume to `helix_artifacts:/app/_bmad-output` and update `artifact_store.py` base path, OR
   - Change worker `_bmad/bmm/config.yaml` `output_folder` to `{project-root}/data/artifacts/_bmad-output` to place artifacts under backend's existing mount.
   ETA: 1 hour including tests.

3. **B-1 (P1):** Add `ARG NEXT_PUBLIC_API_URL` to `frontend/Dockerfile` and wire it through the `next build` step. ETA: 15 minutes.

**Should fix (partial blockers):**

4. **B-9 (P2):** Either lower `backend` and `worker` mem_limit to 700m each (total 3700m, safely under 4 GB), or update the compose comment to recommend e2-standard-2 (8 GB) as minimum for production. ETA: 5 minutes.

**Verification required:**

5. Smoke test on a fresh Ubuntu 24.04 LTS e2-medium GCP VM:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/datainteg/helix-ai-migration/main/setup.sh \
     | sudo bash -s -- --non-interactive --domain helix.example.com
   ```
6. Confirm `worker/requirements.lock` installs cleanly on Linux (`pip install -r worker/requirements.lock` in a `python:3.11-slim` container).
7. Confirm BMAD planning artifact appears via `GET /api/v1/agent-workflows/{id}/artifact-content` after a workflow run.
8. Confirm `NEXT_PUBLIC_API_URL` in browser Network tab points to the VM's external IP, not `localhost`.

---

## 5. Updated Verdict

**⚠️ NEEDS 4–6 MORE HOURS**

Wave-3 closed 5 of 10 blockers cleanly and made real progress on 3 others. Two blockers remain fully open:

- **B-7** (Python version lockfile mismatch) is an INFRA reliability issue: the worker image will install CP313 wheels on a CP311 runtime and may silently pick wrong wheel versions or fail to install `pywin32`. On GCP Linux this is a certain deploy failure for any organization using Vertex AI (since `google-cloud-aiplatform` is absent from the lockfile).
- **B-5** (artifact volume path split) means every BMAD workflow produces artifacts that are immediately lost to the API layer — the artifact content endpoint will 404 on all BMAD outputs.

With B-7 and B-5 fixed (estimated 1.5 engineering-hours combined), the stack is safe for a **team-internal GCP production deploy**. For a public OSS "one-click" announcement, B-1's Dockerfile `ARG` fix and a successful smoke test on a fresh VM are also required.

**Realistic gate to ✅ ship:**
- Close B-7 (lockfile regeneration): 30 min
- Close B-5 (artifact path alignment): 60 min
- Close B-1 fully (Dockerfile ARG): 15 min
- Smoke test on fresh VM: 30 min
- **Total: ~2.5 hours**

**Do NOT ship today** with B-7 open — every Vertex AI workflow will fail silently and the error message will be an `ImportError` buried in worker logs, not a user-visible error.

---

## 6. Appendix — Wave-3 Commit Timeline

All commits are on the `main` branch unless marked `@` (stash/alternate ref).

| Timestamp (IST) | SHA | Agent | Title |
|-----------------|-----|-------|-------|
| 17:13:50 | 6c8fddf4 @ | F4 | fix(docker): backend Dockerfile exec-form PID1, bookworm, unixodbc, dev deps split |
| 17:14:30 | 6ba10b30 | F6 | fix(docker): frontend Dockerfile — deterministic npm ci, node 20.20.2 pin, 30s healthcheck |
| 17:14:53 | bdb735c5 | F5 | fix(worker): W-003 concurrency cap + W-007 graceful shutdown |
| 17:15:06 | 57b19113 | F5 | fix(worker): W-005 heartbeat in monolithic activity + heartbeat strategy comment |
| 17:15:20 | 1c4f1f12 | F5 | fix(worker): W-004 healthcheck TCP probe + 60s start-period |
| 17:17:42 | 321feca0 | F3 | fix(secrets): preserve Fernet = padding in generate-secrets.sh and .ps1 |
| 17:18:16 | 4009a2c4 | F10 | fix(bmad): add runtime assertion for artifact store writability at worker startup |
| 17:18:33 | eed0cadf | F1 | fix(setup): enforce LF on shell + compose files via .gitattributes |
| 17:18:44 | 8134f2b8 | F1 | fix(setup): add scripts/preflight.sh — RAM + disk + port checks |
| 17:19:08 | d29037bc | F1 | fix(setup): distro-aware Docker bootstrap + non-interactive + cloud-IP detect |
| 17:19:23 | 21748dd6 | F1 | fix(setup): setup.ps1 parity — non-interactive, domain, admin-email, UTF-8 noBOM, icacls |
| 17:19:40 | 170c2512 | F1 | fix(setup): operator install snippet + canonical repo URL in DEPLOY/CONTRIBUTING |
| 17:19:47 | 4baa1d62 | F8 | feat(cli): admin bootstrap |
| 17:19:56 | 95644c1b | F3 | fix(secrets): add test_secret_generation.py — Fernet key length + validator regression tests |
| 17:20:04 | 7841c5b1 | F8 | docs: sync README + DEPLOY + INSTALLATION with wave-1/2/3 reality |
| 17:20:08 | 4b264137 | F3 | fix(secrets): append 43-char key runbook addendum to MIGRATION_NOTES.md |
| 17:21:41 | f7f1bd24 @ | F7 | fix(security): add --rotate-secrets CLI orchestrator that actually re-encrypts data |

**Not committed:** F2 (fix(compose):), F9 (fix(deps):)

---

*Report written by WAVE-3 DEPLOY-FIX AGGREGATOR. Read-only. No source code modified.*
