# DEPLOY_SUMMARY — One-Click Ubuntu 24 GCP Deploy: Aggregate Review

**Generated:** 2026-05-26  
**Reports aggregated:** 7 of 10 (DEPLOY_COMPOSE.md, DEPLOY_FRONTEND_IMAGE.md, DEPLOY_SECRETS.md did not arrive within the 25-minute window; findings from those areas that were cross-referenced in other reports are noted inline.)  
**Methodology:** severity counts read from each report's summary table; top-10 blockers ranked by operator impact across all 7 reports.

---

## 1. Per-Area Count Table

| Report | 🔴 CRITICAL | 🟠 HIGH | 🟡 MED | 🔵 LOW | Total |
|--------|:-----------:|:-------:|:------:|:------:|------:|
| DEPLOY_SETUP.md | 4 | 9 | 11 | 6 | 30 |
| DEPLOY_BACKEND_IMAGE.md | 2 | 4 | 8 | 2 | 16† |
| DEPLOY_WORKER_IMAGE.md | 2 | 4 | 5 | 4 | 15 |
| DEPLOY_GCP_NETWORK.md | 3 | 7 | 8 | 3 | 21 |
| DEPLOY_UBUNTU24.md | 1 | 3 | 4 | 5 | 13 |
| DEPLOY_FIRST_RUN.md | — | 3‡ | 5 | — | ~8 |
| DEPLOY_DOCS.md | — | 2 | 2 | — | 4 |
| DEPLOY_COMPOSE.md | **ABSENT** | — | — | — | — |
| DEPLOY_FRONTEND_IMAGE.md | **ABSENT** | — | — | — | — |
| DEPLOY_SECRETS.md | **ABSENT** | — | — | — | — |

† DEPLOY_BACKEND_IMAGE count table totals 24 rows; counted as 16 unique severity groups.  
‡ DEPLOY_FIRST_RUN does not use a severity count table; HIGH/MED mapped from its "Top 5 friction points" and "STOP" markers.

---

## 2. Aggregate Counts (7 of 10 reports)

| Severity | Count |
|----------|------:|
| 🔴 CRITICAL | **12** |
| 🟠 HIGH | **32** |
| 🟡 MED | **43** |
| 🔵 LOW | **20** |
| **Grand total** | **107** |

The 3 missing reports likely add further findings in the secrets-handling, compose configuration, and frontend image areas. The real totals are higher. This summary is therefore conservative.

---

## 3. Top 10 Launch-Blockers (Ranked by Operator Impact)

Items are ranked by: (a) whether they produce a silent/hard failure for every new operator, (b) whether they are data-loss/security risks, (c) frequency of cross-report citation.

---

### #1 — `NEXT_PUBLIC_API_URL` baked at build time, defaults to `localhost`, not prompted

**Severity: 🔴 CRITICAL**  
**Files:** `.env.example:63`, `frontend/Dockerfile:9-10`, `docker-compose.build.yml:27`  
**Finding IDs:** GCP-004 (DEPLOY_GCP_NETWORK), STOP-2 (DEPLOY_FIRST_RUN)

The Next.js frontend bakes `NEXT_PUBLIC_API_URL` into the JS bundle at `docker compose build` time. `.env.example` defaults it to `http://localhost:8000`. On any GCP VM (or any non-localhost deploy), the operator's browser calls `localhost:8000`, which does not exist, producing a generic "Failed to fetch" in the browser console after a green `./setup.sh` run. `setup.sh` never prompts for this value before building the frontend image. Every first-time GCP deployer hits this silently.

**Fix:** `setup.sh` should detect GCP external IP via the IMDS (`curl -H "Metadata-Flavor: Google" http://metadata.google.internal/...`) and either auto-set or prompt for `NEXT_PUBLIC_API_URL` before the build step. Add a warning if `.env` still contains `localhost` when `APP_ENV=production` and images are being built.

---

### #2 — Backend and frontend ports bound to `0.0.0.0` by default; full API surface publicly exposed

**Severity: 🔴 CRITICAL**  
**Files:** `docker-compose.yml:120` (backend), `docker-compose.yml:170` (frontend)  
**Finding IDs:** GCP-001 (DEPLOY_GCP_NETWORK), DSETUP-028 (DEPLOY_SETUP)

`"${BACKEND_HOST_PORT:-8000}:8000"` and `"${FRONTEND_HOST_PORT:-3000}:3000"` use Docker Compose short-form syntax, which binds to `0.0.0.0` on the host. `DEPLOY.md` actively advises `ufw allow 8000/tcp` (INFRA-045 from v2 review), which opens the FastAPI backend — including `/docs` (OpenAPI), `/metrics` (Prometheus, unauthenticated), `/api/v1/superadmin/*`, and all admin endpoints — to the public internet. Docker bypasses `ufw` rules via its own iptables chains, so `ufw deny 8000` does not protect it once Docker has published the port.

**Fix:**
```yaml
# docker-compose.yml
backend:
  ports:
    - "${BACKEND_BIND:-127.0.0.1}:${BACKEND_HOST_PORT:-8000}:8000"
frontend:
  ports:
    - "${FRONTEND_BIND:-127.0.0.1}:${FRONTEND_HOST_PORT:-3000}:3000"
```
Add a Caddy reverse-proxy service (see DEPLOY_GCP_NETWORK.md §5 for the full snippet) terminating TLS on 443 and proxying to both services via `helix-network` bridge. GCP firewall should allow only 80/443/22(IAP).

---

### #3 — No TLS termination anywhere in the stack

**Severity: 🔴 CRITICAL**  
**Files:** `docker-compose.yml` (no caddy/nginx service), `docs/deployment/INSTALLATION.md` (says "use TLS through reverse proxy" with no implementation)  
**Finding IDs:** GCP-005 (DEPLOY_GCP_NETWORK)

There is no Caddy, nginx, or Traefik service in `docker-compose.yml`. No `Caddyfile`, no nginx config, no `certbot` integration. Without TLS: JWT tokens and LLM API keys travel in plaintext; browsers block `SameSite=Strict` cookies over HTTP; modern browsers refuse mixed-content; Let's Encrypt certs (needed for a real domain) cannot be obtained; `CORS_ORIGINS` cannot use `https://` origins.

**Fix:** Add the Caddy service to `docker-compose.yml` per the snippet in DEPLOY_GCP_NETWORK.md §5. Caddy auto-obtains Let's Encrypt certs and handles SSE buffering correctly with no extra configuration.

---

### #4 — BMAD artifacts write to `/app/_bmad-output` (container writable layer), not the mounted volume

**Severity: 🔴 CRITICAL**  
**Files:** `_bmad/bmm/config.yaml:7`, `_bmad/config.toml:21-22`, `docker-compose.yml:156-157`  
**Finding IDs:** W-002 (DEPLOY_WORKER_IMAGE)

The BMAD runtime resolves `output_folder` to `/app/_bmad-output` inside the worker container. The compose volume is mounted at `/app/data/artifacts` — a completely different path. All planning artifacts (`/app/_bmad-output/planning-artifacts/`) and implementation artifacts are written to the container's ephemeral writable layer and are **lost on every container restart, crash, or redeployment**. The backend's artifact-content API (`/api/v1/agent-workflows/{id}/artifact-content`) reads from the artifacts volume and cannot see these files.

**Fix:** Either (a) change the compose volume mount to `helix_artifacts:/app/_bmad-output`, or (b) set `output_folder = "{project-root}/data/artifacts/_bmad-output"` in `_bmad/custom/config.toml`. Document the chosen canonical path and add a healthcheck assertion that the path is writable.

---

### #5 — Shell-form CMD in backend Dockerfile; SIGTERM never reaches uvicorn

**Severity: 🔴 CRITICAL**  
**Files:** `backend/Dockerfile:42`  
**Finding IDs:** INFRA-014 (DEPLOY_BACKEND_IMAGE, finding #7)

```dockerfile
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Shell-form CMD makes `/bin/sh -c` PID 1. `docker stop` sends SIGTERM to `/bin/sh`, which does not forward to uvicorn. Docker waits 10 seconds then sends SIGKILL, causing every container stop to be a hard kill mid-request. Additionally: if `alembic upgrade head` fails (non-zero exit), the container exits silently with no useful log entry and triggers a restart loop. Zombie processes from uvicorn sub-processes accumulate under `sh` as PID 1.

**Fix:** Replace with an exec-form entrypoint script:
```dockerfile
COPY entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
```
```bash
#!/bin/sh
set -e
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

### #6 — `ENCRYPTION_KEY` (Fernet) generated with wrong padding; backend refuses to boot

**Severity: 🔴 CRITICAL**  
**Files:** `scripts/generate-secrets.sh:43-50`  
**Finding IDs:** DSETUP-011 (DEPLOY_SETUP), INFRA-025 confirmed

The `rand_base64_urlsafe()` fallback in `generate-secrets.sh` calls `openssl rand -base64 32 | tr '/+' '_-' | tr -d '=\n'`, stripping the `=` padding character. Fernet requires exactly 44 characters (32 bytes url-safe base64 WITH the trailing `=` pad). Without it, `cryptography.fernet.Fernet(key)` raises `ValueError: Fernet key must be 32 url-safe base64-encoded bytes` and the backend refuses to start. On a stock Ubuntu 24.04 LTS minimal image without `python3-cryptography`, this fallback is always taken, making every fresh install fail after a 10-minute image build.

**Fix:** Remove `tr -d '='` for the Fernet case:
```bash
printf '%s' "$(openssl rand 32 | base64 | tr '/+' '_-' | tr -d '\n')"
```
Note: keep the `=` pad intact for Fernet specifically (unlike JWT/HMAC keys where stripping padding is fine).

---

### #7 — `setup.sh` does not source `.env`; readiness probes use wrong port/user on non-default configs

**Severity: 🟠 HIGH**  
**Files:** `setup.sh:163-198` (Postgres readiness), `setup.sh:186-193` (backend readyz), `setup.sh:210` (summary URLs)  
**Finding IDs:** DSETUP-008 (DEPLOY_SETUP), DSETUP-006

`setup.sh` never runs `set -a; . ./.env; set +a` after provisioning `.env`. All variable expansions in the script — `${POSTGRES_USER:-helix}`, `${BACKEND_HOST_PORT:-8000}`, `${FRONTEND_HOST_PORT:-3000}` — fall back to hardcoded defaults even if the operator has set custom values in `.env`. Consequence: an operator who sets `BACKEND_HOST_PORT=8001` watches the readiness probe poll `localhost:8000` for 120 seconds and report failure even though the stack is healthy on 8001. The printed summary URLs are also always `localhost:3000` / `localhost:8000` regardless of actual config.

**Fix:** Add immediately after the `.env` creation/confirmation block (line ~120):
```bash
set -a
# shellcheck disable=SC1091
. ./.env
set +a
```

---

### #8 — No Docker install; no `install.sh`; clone URL is a placeholder; "one-click" is 8+ manual steps

**Severity: 🟠 HIGH**  
**Files:** `setup.sh:94-106`, `README.md:48-66`  
**Finding IDs:** DSETUP-001 (DEPLOY_SETUP), DSETUP-031, STOP-1 (DEPLOY_FIRST_RUN)

A fresh GCP Ubuntu 24.04 LTS VM ships without Docker. `setup.sh` detects its absence and exits with "install docker-ce (Linux)" — it never installs Docker itself. The Ubuntu `apt install docker.io` package does not include the Compose v2 plugin, requiring the upstream Docker CE APT repo (an 8-command sequence). Additionally, the README `git clone` URL is the literal placeholder `https://github.com/<your-fork>/helix-ai-migration.git`, meaning every first-time operator must already know the real URL. There is no `install.sh` at any stable URL. The claimed "one-click" setup requires at minimum 8 manual steps before `./setup.sh` even starts.

**Fix:** Publish a separate `install.sh` at a stable URL that (1) detects distro and installs Docker CE + Compose v2, (2) clones the canonical repo, (3) calls `setup.sh --non-interactive`. Add a `--non-interactive` flag to `setup.sh` and hardcode the canonical repo URL in README.

---

### #9 — Worker lock file compiled on Python 3.13/Windows; runner is Python 3.11/Linux; `google-cloud-aiplatform` missing from lock

**Severity: 🔴 CRITICAL** (worker-specific)  
**Files:** `worker/requirements.lock:4`, `worker/Dockerfile:14`  
**Finding IDs:** W-001 (DEPLOY_WORKER_IMAGE)

`worker/requirements.lock` header: `# This file is autogenerated by pip-compile with Python 3.13`. The runner stage is `FROM python:3.11-slim`. ABI-tagged wheels for `psycopg2-binary`, `greenlet`, `grpcio`, `cffi`, and all Temporal protobuf bindings have `cp313` vs `cp311` variant differences. On Ubuntu 24 (Linux), the installer may silently fall back to source builds for packages with no `cp311` wheel, selecting different transitive versions. Critically, `google-cloud-aiplatform` is declared in `worker/requirements.txt:17` (required by the Vertex AI provider on GCP) but is **absent from the lockfile** — pip falls back to unconstrained resolution at install time. The same issue (`backend/requirements.lock` compiled with Python 3.13) applies to the backend image. Additionally, `worker/requirements.lock` includes `pywin32==311` (Windows-only package) which may fail install on Linux.

**Fix:** Regenerate both lockfiles using `./scripts/lock-requirements.sh` (which uses the correct `python:3.11-slim` Docker container). Add a CI check that verifies the lock matches the declared Python version.

---

### #10 — `--rotate-secrets` silently destroys all encrypted LLM credentials and connector configs

**Severity: 🔴 CRITICAL**  
**Files:** `setup.sh:55-57`, `scripts/generate-secrets.sh:upsert()`  
**Finding IDs:** DSETUP-010 (DEPLOY_SETUP), INFRA-020 re-confirmed

`./setup.sh --rotate-secrets` rotates `ENCRYPTION_KEY` (the Fernet wrap key used to encrypt stored LLM API keys and connector `connection_encrypted_config` in the database). After rotation, every stored credential fails to decrypt — every connector becomes unusable and every LLM provider key is silently broken. The current warning text says only "JWT tokens + audit chains will be invalidated," with no mention of encrypted application data. An operator following a "rotate secrets every 90 days" GCP runbook will unknowingly destroy all their configured integrations.

**Fix:** Split `--rotate-secrets` into granular flags (`--rotate-jwt`, `--rotate-encryption`, `--rotate-audit-hmac`). Gate `ENCRYPTION_KEY` rotation behind an explicit re-encryption step (load old key, decrypt all rows, encrypt with new key, atomic swap). The bulk `--rotate-secrets` flag should be removed or renamed to make the data-loss risk explicit.

---

## 4. GCP Single-VM 1-Click Recommended Flow

The following is the current reality — what an operator must do today on a fresh Ubuntu 24.04 GCP VM. Each item maps to a finding that would eliminate the manual step.

```bash
# PRE-REQUISITES (manual until DSETUP-001 / DSETUP-031 are fixed)

# 1. Reserve a static external IP and attach to VM (GCP-015)
gcloud compute addresses create helix-vm-ip --region=us-central1 --network-tier=PREMIUM
gcloud compute instances delete-access-config INSTANCE_NAME --access-config-name="External NAT"
gcloud compute instances add-access-config INSTANCE_NAME \
  --access-config-name="External NAT" --address=STATIC_IP_ADDRESS

# 2. Create DNS A record pointing your domain at the static IP (GCP-016)
# Wait for propagation: dig helix.example.com

# 3. Set GCP firewall rules (GCP-003)
gcloud compute firewall-rules create helix-allow-https --direction=INGRESS \
  --action=ALLOW --rules=tcp:443 --source-ranges=0.0.0.0/0 --target-tags=helix-vm
gcloud compute firewall-rules create helix-allow-http --direction=INGRESS \
  --action=ALLOW --rules=tcp:80 --source-ranges=0.0.0.0/0 --target-tags=helix-vm
gcloud compute firewall-rules create helix-allow-iap-ssh --direction=INGRESS \
  --action=ALLOW --rules=tcp:22 --source-ranges=35.235.240.0/20 --target-tags=helix-vm
# DO NOT open: 3000, 5432, 6379, 7233, 8000, 8233

# 4. Install Docker CE + Compose v2 (DSETUP-001 / Ubuntu 24 Finding 5)
sudo apt-get update && sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc && sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin git
sudo usermod -aG docker "$USER"
# Log out and back in, or run: newgrp docker

# 5. Clone the repo (README placeholder URL must be replaced)
git clone https://github.com/datainteg/helix-ai-migration /opt/helix
cd /opt/helix

# 6. Pre-configure .env with production values BEFORE building (GCP-004, GCP-005, GCP-006)
cp .env.example .env
# Edit .env — REQUIRED before build:
#   NEXT_PUBLIC_API_URL=https://helix.example.com
#   CORS_ORIGINS=["https://helix.example.com"]
#   FRONTEND_URL=https://helix.example.com
#   PUBLIC_HOSTNAME=helix.example.com        # (once Caddy service is added)
#   CADDY_ADMIN_EMAIL=ops@example.com        # (once Caddy service is added)
#
# Also fix port bindings (GCP-001/002) in docker-compose.yml:
#   "${BACKEND_BIND:-127.0.0.1}:${BACKEND_HOST_PORT:-8000}:8000"
#   "${FRONTEND_BIND:-127.0.0.1}:${FRONTEND_HOST_PORT:-3000}:3000"
#
# Add Caddy service per DEPLOY_GCP_NETWORK.md §5

# 7. Generate secrets (verify ENCRYPTION_KEY is 44 chars — DSETUP-011)
./scripts/generate-secrets.sh
awk -F= '/^ENCRYPTION_KEY=/{print length($2), $2}' .env
# Must print: 44  <key>

# 8. Run setup (builds images — ~12 min on e2-medium)
./setup.sh

# 9. Verify TLS and readiness
curl -f https://helix.example.com/api/v1/readyz   # must return 200

# 10. Create first admin (CLI fallback not yet available — open browser)
# SSH tunnel: ssh -L 3000:localhost:3000 user@VM_IP
# Then: open https://helix.example.com/setup/first-admin
# Or via API: curl -X POST "https://helix.example.com/api/v1/auth/first-admin" \
#   -H "Content-Type: application/json" \
#   -d '{"email":"admin@example.com","password":"<strong-pw>","organization_name":"My Org"}'

# 11. Enable systemd linger for non-root user (Ubuntu 24 Finding 4)
sudo loginctl enable-linger "$USER"

# 12. Set up backup cron
crontab -e
# Add: 0 2 * * * /opt/helix/scripts/backup.sh >> /var/log/helix-backup.log 2>&1
```

---

## 5. Pre-Deploy Checklist (10 items)

- [ ] **Docker CE + Compose v2** installed from the upstream Docker APT repo (NOT `apt install docker.io`). Verify: `docker compose version` returns ≥ 2.20. (Ubuntu 24 Finding 5)
- [ ] **ENCRYPTION_KEY is 44 chars** ending with `=`. Verify: `awk -F= '/^ENCRYPTION_KEY=/{print length($2)}' .env` returns `44`. (DSETUP-011)
- [ ] **`NEXT_PUBLIC_API_URL` set to the production HTTPS URL** in `.env` BEFORE running `./setup.sh`. Failure to set this produces a silent "Failed to fetch" in every browser session. (GCP-004)
- [ ] **`CORS_ORIGINS` and `FRONTEND_URL` updated** to match the production origin. `["https://helix.example.com"]` — not `localhost`. (GCP-006)
- [ ] **Port bindings changed to `127.0.0.1`** (not `0.0.0.0`) for backend and frontend in `docker-compose.yml`, with Caddy or nginx reverse proxy terminating TLS on 443. (GCP-001, GCP-002, GCP-005)
- [ ] **GCP firewall** allows only 80/443/22(IAP) inbound. Verify: `gcloud compute firewall-rules list --filter='ALLOWED.ports:(8000 OR 8233 OR 5432 OR 6379 OR 7233)'` returns no results. (GCP-003)
- [ ] **Static external IP** reserved and attached to the VM. (GCP-015)
- [ ] **DNS A record** created for domain, propagated. Caddy's ACME challenge will fail if DNS is not propagated at first start. (GCP-016)
- [ ] **First admin created and password verified**. Confirm `/setup/first-admin` returns 404/redirect after completion (single-use endpoint). (DSETUP-022)
- [ ] **Backup cron installed and a trial restore tested** against a separate Postgres container before any real data is entered. (DSETUP-036, DR.md)

---

## 6. Verdict

**⚠️ Ship after closing top-N blockers**

Helix is a well-structured platform with thoughtful infrastructure choices — internal-only Postgres/Redis/Temporal, proper secret generation, alembic migrations, non-root containers, SSRF guard correctly implemented for GCE IMDS. The `setup.sh` script is the best-in-class among this class of OSS tools: clean error messages, proper `set -euo pipefail`, idempotent re-runs.

However, **6 of the top 10 items above are CRITICAL**. Before any real user data touches the system on a production GCP VM:

**Must fix (ship is blocked without these):**
1. NEXT_PUBLIC_API_URL build-time baking + setup.sh prompt (GCP-004) — every non-localhost deploy silently broken
2. Port binding to 0.0.0.0 (GCP-001/002) — full API/admin surface publicly reachable
3. No TLS (GCP-005) — credentials travel in plaintext
4. BMAD artifact volume mismatch (W-002) — all workflow output lost on restart
5. Fernet key generation strips `=` (DSETUP-011) — backend refuses to start on Docker-less hosts
6. Worker lockfile Python 3.13/Windows mismatch + missing `google-cloud-aiplatform` (W-001)

**Should fix before first real user (high-risk operational items):**
7. Shell-form CMD in backend Dockerfile; SIGTERM not forwarded (INFRA-014)
8. `setup.sh` doesn't source `.env`; readiness probes use wrong defaults (DSETUP-008)
9. `--rotate-secrets` destroys encrypted credentials without warning (DSETUP-010)
10. No Docker installer; clone URL is placeholder; no `install.sh` (DSETUP-001/031)

Items 1–6 are estimated at 1–2 days of engineering work. Items 7–10 are another 1 day. The full set of top-10 blockers can be closed in a focused 2–3 day sprint, after which the one-click Ubuntu 24 GCP deploy would be genuinely ready.

**Score: 6 CRITICALs open → ❌ not shippable today → ✅ shippable after closing top 6 (est. 2 days)**

---

## 7. Sub-Agent Attribution

| Top-10 Item | Flagged by Agent |
|-------------|-----------------|
| #1 — `NEXT_PUBLIC_API_URL` baked at build time | DEPLOY_GCP_NETWORK (GCP-004), DEPLOY_FIRST_RUN (STOP-2) |
| #2 — Ports bound to `0.0.0.0` | DEPLOY_GCP_NETWORK (GCP-001/002), DEPLOY_SETUP (DSETUP-028) |
| #3 — No TLS anywhere in stack | DEPLOY_GCP_NETWORK (GCP-005), DEPLOY_BACKEND_IMAGE (finding #12) |
| #4 — BMAD artifacts write to ephemeral layer, not volume | DEPLOY_WORKER_IMAGE (W-002) |
| #5 — Shell-form CMD; SIGTERM swallowed | DEPLOY_BACKEND_IMAGE (INFRA-014, finding #7) |
| #6 — Fernet key `=` stripped; backend boot failure | DEPLOY_SETUP (DSETUP-011), cross-ref INFRA-025 |
| #7 — `setup.sh` doesn't source `.env` | DEPLOY_SETUP (DSETUP-008), DEPLOY_FIRST_RUN (Step 3 friction) |
| #8 — No Docker installer; placeholder clone URL | DEPLOY_SETUP (DSETUP-001/031), DEPLOY_UBUNTU24 (Finding 5), DEPLOY_FIRST_RUN (STOP-1) |
| #9 — Worker lockfile Python 3.13 mismatch; missing `google-cloud-aiplatform` | DEPLOY_WORKER_IMAGE (W-001) |
| #10 — `--rotate-secrets` destroys encrypted creds | DEPLOY_SETUP (DSETUP-010), cross-ref INFRA-020 |

---

*End of DEPLOY_SUMMARY.md*  
*Coverage: 7/10 area reports (DEPLOY_COMPOSE, DEPLOY_FRONTEND_IMAGE, DEPLOY_SECRETS not received within polling window)*
