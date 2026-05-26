# DEPLOY_COMPOSE — Docker Compose Production-Deploy Audit
## Target: Ubuntu 24.04 LTS on GCP e2-medium (2 vCPU / 4 GB RAM)

> Generated 2026-05-26. Scope limited to `docker-compose.yml`,
> `docker-compose.dev.yml`, `docker-compose.build.yml`, and `.env.example`.
> Prior findings INFRA-001–INFRA-013 are referenced below and re-assessed
> for closure/regression status.
>
> Severity legend: 🔴 CRITICAL · 🟠 HIGH · 🟡 MED · 🔵 LOW

---

## 1. File inventory & compose-validate results

| File | Lines | `docker compose config` |
|---|---|---|
| `docker-compose.yml` | 192 | clean ✅ |
| `docker-compose.dev.yml` | 58 | clean ✅ |
| `docker-compose.build.yml` | 27 | clean ✅ |
| All three combined | — | clean ✅ |

```
docker compose -f docker-compose.yml config --quiet   → exit 0
docker compose -f docker-compose.yml -f docker-compose.dev.yml config --quiet → exit 0
docker compose -f docker-compose.yml -f docker-compose.build.yml config --quiet → exit 0
docker compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.build.yml config --quiet → exit 0
```

**compose validate clean ✅ / has 0 schema errors**

---

## 2. Findings — re-audit of INFRA-001 to INFRA-013

### DC-001 (was INFRA-001) — `deploy.resources.limits` still ignored on `docker compose up`

🔴 **NOT FIXED — REGRESSION / STILL OPEN**

`docker-compose.yml` still uses only `deploy.resources.limits.memory`
for every service. `mem_limit:` / `cpus:` top-level keys are absent.
`docker compose config` confirms the `deploy:` block is still the only
constraint.

```yaml
# docker-compose.yml lines 35-38
deploy:
  resources:
    limits:
      memory: 1G   # ← silently ignored by docker compose up
```

Same pattern at lines 53-56 (redis), 80-83 (temporal), 110-113
(temporal-ui), 140-143 (backend), 160-163 (worker), 178-181 (frontend).

**Impact on GCP e2-medium:** If limits were enforced the declared total
would be **4,864 MB** (see §3, DC-009 below), already 768 MB over the
4 GB host. Because the limits are silently ignored, no container is
capped — a single runaway worker or temporal can OOM the host and
trigger an involuntary kernel OOM-kill cascade.

**Fix:** Add `mem_limit:` and `cpus:` top-level keys per service (these
ARE honoured by `docker compose up`) and rebalance allocations to fit
within the 4 GB constraint:

```yaml
# Recommended replacement (drop the deploy: block, add top-level keys):
services:
  postgres:
    mem_limit: 768m
    cpus: "0.5"
  redis:
    mem_limit: 256m
    cpus: "0.25"
  temporal:
    mem_limit: 768m
    cpus: "0.75"
  backend:
    mem_limit: 768m
    cpus: "0.75"
  worker:
    mem_limit: 768m
    cpus: "0.75"
  frontend:
    mem_limit: 384m
    cpus: "0.25"
# Total: 3712 MB — leaves ~384 MB OS headroom on a 4 GB host.
```

---

### DC-002 (was INFRA-002) — `:latest` image tag default

🟠 **NOT FIXED — STILL OPEN**

`docker-compose.yml` line 14:

```yaml
x-image-tag: &image-tag ${HELIX_IMAGE_TAG:-latest}
```

And rendered at config-time:

```
image: helix/backend:latest
image: helix/frontend:latest
image: helix/worker:latest
```

A `docker compose pull` on the GCP VM will silently roll all three
application images to whatever the registry currently labels `latest`.
No operator warning, no version pinning.

**Fix:** Change the fallback to a known release tag or require the
variable:

```yaml
x-image-tag: &image-tag ${HELIX_IMAGE_TAG:?Set HELIX_IMAGE_TAG (e.g. v0.5.0) — :latest is not safe for production}
```

---

### DC-003 (was INFRA-003) — Third-party images pinned to minor version only

🟠 **NOT FIXED — STILL OPEN**

```
image: postgres:16.4          # docker-compose.yml line 18
image: redis:7.4-alpine       # line 41
image: temporalio/auto-setup:1.25.0  # line 59
image: temporalio/ui:2.31.2   # line 89
```

None include an `@sha256:` digest. A supply-chain compromise at the
registry can serve a patched binary without changing the tag. For a
production GCP VM, lock each third-party image to a digest:

```yaml
image: postgres:16.4@sha256:<digest>
image: redis:7.4-alpine@sha256:<digest>
```

Fetch current digests via `docker pull --quiet <image> && docker inspect
--format='{{index .RepoDigests 0}}' <image>`.

---

### DC-004 (was INFRA-004) — Redis healthcheck does not gate writability

🟡 **NOT FIXED — STILL OPEN**

`docker-compose.yml` lines 47-51:

```yaml
healthcheck:
  test: ["CMD", "redis-cli", "ping"]
```

`redis-cli ping` returns `PONG` while Redis is in BGSAVE, loading an
RDB snapshot, or restoring from AOF. Backend and worker start as soon
as this check passes, but can receive `LOADING` errors on write. Fix:

```yaml
test: ["CMD-SHELL", "redis-cli ping | grep -q PONG && redis-cli set healthcheck 1 > /dev/null"]
```

---

### DC-005 (was INFRA-005) — Worker `start_period` absent from compose healthcheck

🟡 **PARTIALLY ADDRESSED — DOCKERFILE ONLY**

`worker/Dockerfile` line 40 sets `start-period=30s` in the Dockerfile
`HEALTHCHECK`. However, `docker-compose.yml` defines **no** `healthcheck:`
block for the worker service at all (confirmed by `docker compose config`
— `worker: has_healthcheck=False`). The Dockerfile `HEALTHCHECK` is
inherited, but there is no compose-level `start_period` override.

More critically: **backend waits for `worker: condition:
service_healthy`**. Because compose inherits the Dockerfile healthcheck
with `start_period=30s`, cold-start on a small VM (heavy imports: `app.
services.workflow_service`, Temporal client, LangGraph, PydanticAI) may
exhaust the window before the process is ready. Bump to 60 s in compose:

```yaml
worker:
  healthcheck:
    start_period: 60s
    interval: 30s
    timeout: 10s
    retries: 3
```

---

### DC-006 (was INFRA-006) — Temporal healthcheck `|| true` always passes

🟡 **NOT FIXED — STILL OPEN**

`docker-compose.yml` lines 73-78:

```yaml
test: ["CMD-SHELL", "tctl --address temporal:7233 cluster health 2>/dev/null || temporal operator cluster health --address temporal:7233 2>/dev/null || true"]
```

The trailing `|| true` means the check always exits 0. Temporal can be
wedged (database schema not applied, listen socket not yet bound) and
the healthcheck still reports healthy. Backend and worker proceed to
connect and fail silently.

**Fix:** Drop `|| true` and let both CLI paths fail:

```yaml
test: ["CMD-SHELL", "tctl --address temporal:7233 cluster health 2>/dev/null || temporal operator cluster health --address temporal:7233"]
```

---

### DC-007 (was INFRA-007) — Shared artifact volume with S3 path

🔵 **ACKNOWLEDGED — LOW IMPACT — NO CHANGE REQUIRED**

`docker-compose.yml` mounts `helix_artifacts` in both backend (line 131)
and worker (line 157). When `ARTIFACT_STORAGE_PROVIDER=s3`, the local
volume mount is dead weight but harmless. `.env.example` now documents
both paths. No code fix needed; operator documentation is adequate.

---

### DC-008 (was INFRA-008) — No `init: true` on Python services

🟡 **NOT FIXED — STILL OPEN (promoted from LOW)**

`docker compose config` confirms:

```
backend: init=NONE
worker:  init=NONE
frontend: init=NONE
```

Additionally, `backend/Dockerfile` line 42 uses **shell-form CMD**:

```dockerfile
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

PID 1 is `/bin/sh -c`. SIGTERM goes to the shell, not to uvicorn.
On `docker compose stop` or GCP instance restart, containers wait the
full 10-second default `stop_grace_period` before SIGKILL. For a
production VM this causes dirty shutdowns and Alembic lock tables.

**Fix (both):**

1. Add to every Python and Node service in `docker-compose.yml`:
   ```yaml
   init: true
   ```
2. Fix backend CMD to exec form:
   ```dockerfile
   CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
   ```

---

### DC-009 (was INFRA-009) — Fixed `container_name:` blocks multi-stack

🔵 **NOT FIXED — BY DESIGN FOR SINGLE-HOST — DOCUMENT**

All six services have hard-coded `container_name:` values. On an
e2-medium running exactly one Helix stack this is acceptable. However,
if operators attempt blue/green or run a staging copy alongside prod,
Docker will reject startup with "Conflict. The container name
'/helix-backend' is already in use."

No code fix needed for single-host. The DEPLOY.md should note: "Running
two stacks on one host requires removing `container_name:` from
`docker-compose.yml` or using distinct `COMPOSE_PROJECT_NAME` values."

---

### DC-010 (was INFRA-010) — Temporal UI 256 MB cap

🔵 **SCOPE-CHANGED — SEE DC-001 / DC-009-MEM**

The `deploy.resources.limits.memory: 256M` at `docker-compose.yml`
lines 110-113 is currently silently ignored (same as DC-001). When
DC-001 is fixed, 256 MB is tight for `temporalio/ui:2.31.2` on long
sessions. Bump to 384 MB in the rebalanced allocation table in DC-001.

---

### DC-011 (was INFRA-011) — `NEXT_PUBLIC_API_URL` baked at build time

🔵 **NOT FIXED — COMMENT INSUFFICIENT**

`docker-compose.build.yml` line 27:

```yaml
args:
  NEXT_PUBLIC_API_URL: ${NEXT_PUBLIC_API_URL:-http://localhost:8000}
```

The default `http://localhost:8000` will be baked into the frontend
image when an operator builds on GCP without setting `NEXT_PUBLIC_API_URL`.
Every API call from the browser will then attempt to reach `localhost:8000`
on the user's laptop, not the server.

**Fix:** Change the fallback to an obvious sentinel that will fail at
build time:

```yaml
args:
  NEXT_PUBLIC_API_URL: ${NEXT_PUBLIC_API_URL:?Set NEXT_PUBLIC_API_URL before building (e.g. https://api.yourdomain.com)}
```

---

### DC-012 (was INFRA-012) — Incomplete `temporal-ui:` block in `docker-compose.dev.yml`

🟠 **NOT FIXED — STILL OPEN**

`docker-compose.dev.yml` line 57-58:

```yaml
  temporal-ui:
    container_name: helix-temporal-ui-dev
```

The block overrides only `container_name:`. It does not:
- Override `profiles:` — so temporal-ui still requires `--profile debug`
  even in the dev overlay.
- Add `ports:` — so developers cannot reach the UI at all without
  `TEMPORAL_UI_BIND=` override.

This is a no-op block that misleads developers. Either delete it or
complete it:

```yaml
  temporal-ui:
    container_name: helix-temporal-ui-dev
    profiles: []   # remove profile gate in dev
    ports:
      - "127.0.0.1:${TEMPORAL_UI_HOST_PORT:-8233}:8080"
```

---

### DC-013 (was INFRA-013) — Dev overlay binds Postgres/Redis/Temporal on 0.0.0.0

🟠 **NOT FIXED — STILL OPEN (HIGH on GCP)**

`docker-compose.dev.yml` lines 43-54:

```yaml
  postgres:
    ports:
      - "${POSTGRES_DEV_HOST_PORT:-5432}:5432"   # binds 0.0.0.0

  redis:
    ports:
      - "${REDIS_DEV_HOST_PORT:-6379}:6379"       # binds 0.0.0.0

  temporal:
    ports:
      - "${TEMPORAL_DEV_HOST_PORT:-7233}:7233"    # binds 0.0.0.0
```

`docker compose config` confirms no `host_ip` field is set, meaning
Docker binds these on all interfaces. On a GCP VM where the operator
accidentally passes `-f docker-compose.dev.yml` in production (or
follows dev docs on a VPS), Postgres port 5432 and Redis 6379 become
publicly accessible if the GCP firewall allows them.

**Fix:** Prefix all dev `ports:` entries with the loopback address:

```yaml
ports:
  - "127.0.0.1:${POSTGRES_DEV_HOST_PORT:-5432}:5432"
  - "127.0.0.1:${REDIS_DEV_HOST_PORT:-6379}:6379"
  - "127.0.0.1:${TEMPORAL_DEV_HOST_PORT:-7233}:7233"
```

---

## 3. New findings (not in INFRA-001–013)

### DC-014 — No logging driver configured; GCP VM disk will fill

🟠 **NEW — HIGH**

Neither `docker-compose.yml` nor any overlay sets a `logging:` block.
Docker defaults to `json-file` with **no rotation**. On a GCP e2-medium
with a 10–30 GB boot disk, verbose Temporal auto-setup and uvicorn access
logs will consume available disk space within days to weeks depending on
traffic.

`docker compose config` confirms:

```
backend: logging=NONE
worker:  logging=NONE
temporal: logging=NONE
(all others also NONE)
```

**Fix:** Add a `logging:` block to every service (or define an
`x-logging` YAML anchor and reference it):

```yaml
x-logging: &default-logging
  driver: json-file
  options:
    max-size: "20m"
    max-file: "5"

services:
  postgres:
    logging: *default-logging
  redis:
    logging: *default-logging
  temporal:
    logging: *default-logging
  backend:
    logging: *default-logging
  worker:
    logging: *default-logging
  frontend:
    logging: *default-logging
```

This caps log storage at ~100 MB per service (600 MB total), leaving
GCP VM disk safe.

---

### DC-015 — Resource budget exceeds GCP e2-medium capacity even with limits

🔴 **NEW — CRITICAL for GCP e2-medium**

Even if DC-001 (`deploy.resources.limits`) were fixed today, the
declared limits **already exceed the host's 4 GB RAM**:

| Service | Declared `mem_limit` |
|---|---|
| postgres | 1,024 MB |
| redis | 256 MB |
| temporal | 1,024 MB |
| backend | 1,024 MB |
| worker | 1,024 MB |
| frontend | 512 MB |
| **Total** | **4,864 MB** |
| **e2-medium** | **4,096 MB** |
| **Deficit** | **−768 MB** |

The OS, kernel page tables, Docker daemon, and host sshd collectively
need ~300–500 MB. Real overcommit is **~1.2–1.3 GB** over a safe
threshold. Temporal (`temporalio/auto-setup`) is particularly heavy —
it embeds a full Go runtime, a Cassandra-compatible persistence layer
on Postgres, and an in-process task-queue scheduler; typical RSS on
first run is 700–900 MB.

**Recommended ceiling for e2-medium (all-in-one deploy):**

```
postgres:  768 MB   (PG shared_buffers = 192 MB, effective_cache_size = 512 MB)
redis:     256 MB
temporal:  768 MB
backend:   768 MB
worker:    768 MB
frontend:  384 MB
──────────────────
Total:   3,712 MB   → 384 MB OS headroom
```

For any expected traffic beyond a handful of concurrent users, consider
an **e2-standard-2 (2 vCPU / 8 GB)** GCP instance, or offload Temporal
to a managed service.

---

### DC-016 — Frontend healthcheck absent at compose level; `depends_on: service_healthy` on frontend succeeds vacuously

🟡 **NEW — MED**

`docker compose config` shows:

```
frontend: has_healthcheck=False
```

The `frontend/Dockerfile` line 28 defines a `HEALTHCHECK` instruction,
so the image does carry one. But the compose `depends_on:` for the
frontend service is:

```yaml
# docker-compose.yml line 174-176
depends_on:
  backend:
    condition: service_healthy
```

Nothing else depends on `frontend: condition: service_healthy`, so the
missing compose-level block is only cosmetic for now. However, without a
compose-level `healthcheck:` block the service appears as
`has_healthcheck=False` in `docker compose ps`, which misleads
operators. Add:

```yaml
frontend:
  healthcheck:
    test: ["CMD", "node", "-e", "fetch('http://localhost:3000/api/healthz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"]
    interval: 30s
    timeout: 5s
    start_period: 30s
    retries: 3
```

---

### DC-017 — Worker has no compose-level healthcheck; `depends_on: service_healthy` gates frontend

🟡 **NEW — MED**

`docker compose config` shows `worker: has_healthcheck=False`. The
Dockerfile `HEALTHCHECK` is inherited (makes a live Temporal connection
every 30 s — see also INFRA-017), but compose does not define a
`healthcheck:` block. This means:

- `docker compose ps` shows worker health as `starting` indefinitely
  until Temporal responds.
- The Temporal connection probe creates a fresh TLS handshake every 30 s
  (INFRA-017 from REVIEW_INFRA.md, still open).

Add a compose-level healthcheck with a suitable `start_period` (60 s
recommended per DC-005) and switch the probe to a lightweight liveness
check that does not open a Temporal connection on every interval.

---

### DC-018 — Backend `depends_on: temporal: condition: service_started` (not `service_healthy`)

🟡 **NEW — MED**

`docker-compose.yml` line 129-130:

```yaml
temporal:
  condition: service_started
```

Temporal's own healthcheck (`start_period: 30s`, `retries: 5`) is
defined, but backend only waits for Temporal to have **started its
container process**, not for Temporal to be **ready to accept gRPC
connections**. On cold boot of a fresh Postgres schema, Temporal
auto-setup runs schema migrations that can take 20–45 seconds. Backend
will boot, fail the Temporal connection on startup, log an error, and
potentially mark workflows as unhealthy before recovering.

**Fix:** Promote the condition:

```yaml
depends_on:
  temporal:
    condition: service_healthy   # wait for tctl / temporal cluster health
```

Note: DC-006 (the `|| true` fallback) must also be fixed first or
`service_healthy` on temporal is still vacuous.

---

### DC-019 — `/data` mount is a Docker named volume, not a host bind mount

🔵 **NEW — LOW (informational)**

`helix_artifacts` and `helix_postgres_data` are both Docker-managed
named volumes (`driver: local`, `docker-compose.yml` lines 183-187).
On a GCP VM:

**Pros:**
- Docker manages permissions and UID mapping automatically.
- No SELinux `:Z` flag needed (Ubuntu 24.04 uses AppArmor, not SELinux
  by default — so no `:Z` labelling is required on this target OS).
- `docker volume inspect helix_artifacts` reveals the actual host path
  (typically `/var/lib/docker/volumes/helix-ai-migration_helix_artifacts/_data`).

**Cons:**
- Backup script (`scripts/backup.sh`) must use `docker run --rm -v ...`
  to export the volume — it cannot be `rsync`'d directly from the host
  without root access to `/var/lib/docker/`.
- GCP persistent disk must be mounted at `/var/lib/docker` (or Docker
  root changed via `/etc/docker/daemon.json`) to ensure volume data
  survives a boot-disk replacement.

**Recommendation:** In `DEPLOY.md`, document that operators should
mount a GCP persistent disk at `/var/lib/docker/volumes` (or at `/mnt/
helix-data` with Docker root relocated) before running `docker compose
up` for the first time, to ensure volume durability across instance
recreation.

---

### DC-020 — Dev overlay leaks `APP_ENV=development` if accidentally included in prod

🟠 **NEW — HIGH**

`docker-compose.dev.yml` lines 18, 28:

```yaml
backend:
  environment:
    APP_ENV: development
worker:
  environment:
    APP_ENV: development
```

If an operator runs:

```
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

(which the dev overlay docs say is the correct dev invocation), and
runs it on the GCP VM by mistake, the backend starts in development
mode. `APP_ENV=development` in `backend/app/core/config.py` typically
disables security guards (CORS wildcard, relaxed JWT validation, debug
endpoints enabled, `change_me` placeholder secrets accepted).

The comment at the top of `docker-compose.dev.yml` reads "All
credentials come from .env. Use scripts/generate-secrets.sh first."
— this is insufficient: a developer who copies a `screen` session
or CI snippet onto the prod VM may combine both files without realising.

**Fix:**

1. Add a `COMPOSE_FILE` variable to `.env.example` that explicitly
   sets only `docker-compose.yml` for production:
   ```
   COMPOSE_FILE=docker-compose.yml
   ```
2. Or add a guard at the top of `docker-compose.dev.yml`:
   ```yaml
   # DEV ONLY — never pass this file to a production docker compose invocation.
   # Safe guard: if APP_ENV is already set to 'production' in the shell,
   # this override wins and will break prod — you have been warned.
   ```

---

### DC-021 — `TEMPORAL_UI_USERNAME=admin` default in `.env.example`

🟡 **NEW — MED (regression of INFRA-039)**

`.env.example` line 39:

```
TEMPORAL_UI_USERNAME=admin
```

This was flagged as INFRA-039 in REVIEW_INFRA.md (`TEMPORAL_AUTH_ENABLED=
false` default). Still unresolved. Additionally, `docker-compose.yml`
lines 102-103 set `TEMPORAL_AUTH_ENABLED=${TEMPORAL_AUTH_ENABLED:-false}`.

The combination means temporal-ui is passwordless by default. Because
the service is profile-gated to `debug` (good), the risk is lower than
INFRA-039 suggested — but the moment an operator enables the profile on
a GCP VM and adjusts `TEMPORAL_UI_BIND`, the UI is unauthenticated.

**Fix:** Change `.env.example` line 40 default:

```
TEMPORAL_AUTH_ENABLED=true
```

And require `TEMPORAL_UI_PASSWORD` to be non-empty when `TEMPORAL_AUTH_ENABLED=true`.

---

### DC-022 — Backend port 8000 bound on 0.0.0.0 with no loopback option

🟠 **NEW — HIGH**

`docker-compose.yml` lines 119-120:

```yaml
ports:
  - "${BACKEND_HOST_PORT:-8000}:8000"
```

No `host_ip` prefix. Docker binds port 8000 on all interfaces
(`0.0.0.0:8000`). On a GCP VM the backend API (including `/docs`,
`/redoc`, `/openapi.json`, and all data endpoints) is publicly
reachable unless GCP VPC firewall rules block port 8000.

DEPLOY.md (INFRA-045, not yet fixed) still recommends `ufw allow
8000/tcp`. If an operator follows that guide, they will intentionally
open port 8000 to the public internet.

**Fix:** Change the binding to loopback-only and document that a
reverse proxy (nginx/Caddy) should sit in front:

```yaml
ports:
  - "127.0.0.1:${BACKEND_HOST_PORT:-8000}:8000"
```

Or, if direct access is needed temporarily during setup, explicitly
document the firewall requirement and remove the `ufw allow 8000/tcp`
suggestion from DEPLOY.md.

---

### DC-023 — No `stop_grace_period` set; default 10 s is insufficient for Postgres checkpoint

🟡 **NEW — MED**

`docker-compose.yml` sets `restart: unless-stopped` on postgres but no
`stop_grace_period`. Docker's default is 10 s. Postgres performs a
clean checkpoint before shutdown; on a 1 GB heap with active writes this
can take 15–30 s. If Docker kills Postgres before the checkpoint
completes, the next startup triggers crash recovery (WAL replay), adding
30–120 s to boot time.

**Fix:**

```yaml
postgres:
  stop_grace_period: 60s
```

Similarly, temporal auto-setup graceful stop can take >10 s when it
waits for active workflow tasks to drain. Add `stop_grace_period: 30s`
on temporal.

---

### DC-024 — `docker-compose.build.yml` has no `platform:` directive; builds on ARM GCP fail

🟡 **NEW — MED**

`docker-compose.build.yml` and all three Dockerfiles specify no
`platform:` target. GCP offers both x86-64 (`linux/amd64`) and
ARM-based (`linux/arm64`, T2A instances) VMs. If an operator builds on
an ARM Mac (Apple Silicon) or GCP T2A without specifying platform, the
resulting images will be `linux/arm64`. When deployed to an e2-medium
(`linux/amd64`), Docker will either refuse to start the container or
run via slow QEMU emulation.

**Fix:** Add platform to the build overlay:

```yaml
# docker-compose.build.yml
services:
  backend:
    build:
      platform: linux/amd64
      ...
  worker:
    build:
      platform: linux/amd64
      ...
  frontend:
    build:
      platform: linux/amd64
      ...
```

---

### DC-025 — `depends_on` chain creates a long serial cold-boot latency on first run

🔵 **NEW — LOW (informational)**

The full dependency chain on first boot is:

```
postgres (healthcheck 50s max) →
temporal auto-setup (schema migrations, start_period=30s, retries=5 × 15s = up to 105s) →
backend (start_period=30s, waits for temporal: service_started) →
worker (depends_on: backend: service_healthy, start_period=30s) →
frontend (depends_on: backend: service_healthy)
```

Conservative worst-case cold-start: **4–6 minutes** before frontend
is accepting requests. This is expected for a single-host stack with
Temporal schema setup, but operators will perceive it as a hang.

**Document in DEPLOY.md:** Expected cold-boot time on fresh install is
4–6 minutes. Monitor with `docker compose logs -f temporal` and wait for
`INFO` schema-ready messages before testing the frontend.

---

## 4. Summary table

| ID | Severity | Topic | Status vs v2 |
|---|---|---|---|
| DC-001 | 🔴 CRITICAL | `deploy.resources.limits` still ignored | Unchanged ❌ |
| DC-015 | 🔴 CRITICAL | Memory budget exceeds e2-medium (4,864 MB > 4,096 MB) | **New** |
| DC-002 | 🟠 HIGH | `:latest` image tag default | Unchanged ❌ |
| DC-003 | 🟠 HIGH | Third-party images not digest-pinned | Unchanged ❌ |
| DC-012 | 🟠 HIGH | Incomplete `temporal-ui:` dev override block | Unchanged ❌ |
| DC-013 | 🟠 HIGH | Dev overlay binds infra on 0.0.0.0 | Unchanged ❌ |
| DC-014 | 🟠 HIGH | No logging driver / rotation configured | **New** |
| DC-020 | 🟠 HIGH | Dev overlay leaks `APP_ENV=development` into prod | **New** |
| DC-022 | 🟠 HIGH | Backend port 8000 bound on 0.0.0.0 | **New** |
| DC-004 | 🟡 MED | Redis healthcheck does not gate writability | Unchanged ❌ |
| DC-005 | 🟡 MED | Worker `start_period` absent from compose | Partially fixed ⚠️ |
| DC-006 | 🟡 MED | Temporal healthcheck `\|\| true` always passes | Unchanged ❌ |
| DC-008 | 🟡 MED | No `init: true` on Python/Node services (promoted) | Unchanged ❌ |
| DC-011 | 🟡 MED | `NEXT_PUBLIC_API_URL` default bakes `localhost:8000` | Unchanged ❌ |
| DC-016 | 🟡 MED | Frontend healthcheck missing at compose level | **New** |
| DC-017 | 🟡 MED | Worker healthcheck missing at compose level | **New** |
| DC-018 | 🟡 MED | Backend waits for `temporal: service_started` not `service_healthy` | **New** |
| DC-021 | 🟡 MED | `TEMPORAL_UI_USERNAME=admin` default, auth off by default | Unchanged ❌ |
| DC-023 | 🟡 MED | No `stop_grace_period` for Postgres / Temporal | **New** |
| DC-024 | 🟡 MED | No `platform:` in build overlay — ARM/x86 mismatch risk | **New** |
| DC-007 | 🔵 LOW | Shared artifact volume (S3 path documented) | Closed ✅ |
| DC-009 | 🔵 LOW | Fixed `container_name:` blocks multi-stack | By design — document |
| DC-010 | 🔵 LOW | Temporal UI 256 MB (absorbed into DC-015) | Scope-changed |
| DC-019 | 🔵 LOW | Named volumes on GCP — backup path and disk mount | **New** |
| DC-025 | 🔵 LOW | Long cold-boot chain (4–6 min) undocumented | **New** |

**Severity totals:**

| Severity | Count |
|---|---|
| 🔴 CRITICAL | 2 |
| 🟠 HIGH | 7 |
| 🟡 MED | 10 |
| 🔵 LOW | 4 |
| **Total** | **23** |

---

## 5. Compose validate verdict

```
compose validate clean ✅ / has 0 errors
```

All three compose files pass `docker compose config --quiet` individually
and in combination. There are no YAML syntax errors, missing required
fields, or schema violations. The failures identified above are all
**runtime or operational correctness** issues, not schema issues.

---

## 6. Recommended production deploy command sequence (GCP Ubuntu 24.04)

```bash
# 0. Pre-flight
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-plugin

# 1. Attach and mount a GCP persistent disk for Docker volumes
#    (prevents data loss on boot-disk recreation)
sudo mkfs.ext4 /dev/sdb
sudo mkdir -p /mnt/docker-data
sudo mount /dev/sdb /mnt/docker-data
sudo bash -c 'echo "/dev/sdb /mnt/docker-data ext4 defaults 0 2" >> /etc/fstab'
sudo mkdir -p /mnt/docker-data/volumes
sudo bash -c 'echo '"'"'{"data-root": "/mnt/docker-data"}'"'"' > /etc/docker/daemon.json'
sudo systemctl restart docker

# 2. Clone and configure secrets
git clone https://github.com/<your-org>/helix-ai-migration.git /opt/helix
cd /opt/helix
cp .env.example .env
./scripts/generate-secrets.sh
chmod 600 .env

# 3. Set required production env vars (edit .env)
#    HELIX_IMAGE_TAG=v0.5.0          (not :latest)
#    HELIX_IMAGE_PREFIX=ghcr.io/your-org
#    APP_ENV=production
#    NEXT_PUBLIC_API_URL=https://api.yourdomain.com
#    CORS_ORIGINS=["https://yourdomain.com"]
#    TEMPORAL_AUTH_ENABLED=true
#    TEMPORAL_UI_BIND=127.0.0.1      (default — do not change unless behind proxy)

# 4. Pull pre-built images (or build from source with docker-compose.build.yml)
docker compose -f docker-compose.yml pull

# 5. Start infrastructure first; verify postgres and redis healthy before proceeding
docker compose -f docker-compose.yml up -d postgres redis
docker compose -f docker-compose.yml ps   # wait for healthy

# 6. Start temporal; wait for schema setup (~60-90 s on first run)
docker compose -f docker-compose.yml up -d temporal
docker compose -f docker-compose.yml logs -f temporal 2>&1 | grep -m1 "schema setup complete\|all namespaces are healthy"

# 7. Start application services
docker compose -f docker-compose.yml up -d backend worker frontend

# 8. Verify stack health
docker compose -f docker-compose.yml ps
curl -f http://localhost:8000/api/v1/health
curl -f http://localhost:3000/api/healthz

# 9. (Optional) Enable Temporal UI debug access — loopback only
docker compose -f docker-compose.yml --profile debug up -d temporal-ui
# Access via SSH tunnel: ssh -L 8233:127.0.0.1:8233 <vm-ip>
# Then open http://localhost:8233 locally

# 10. Install log rotation (until DC-014 is fixed in compose)
sudo bash -c 'cat > /etc/docker/daemon.json <<EOF
{
  "data-root": "/mnt/docker-data",
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "20m",
    "max-file": "5"
  }
}
EOF'
sudo systemctl restart docker
# Note: daemon.json log-opts apply only to NEW containers; existing containers
# require recreation or per-service logging: blocks in docker-compose.yml.

# 11. Schedule backup cron
echo "0 3 * * * cd /opt/helix && ./scripts/backup.sh >> /var/log/helix-backup.log 2>&1" | sudo tee /etc/cron.d/helix-backup
```

---

## 7. Top-5 fixes before go-live on GCP

1. **🔴 DC-001 + DC-015 — Replace `deploy.resources.limits` with `mem_limit:` / `cpus:` AND rebalance to ≤ 3,712 MB total.** Without this, no container is capped; the memory budget is already 768 MB over the host ceiling even with limits. Both issues are one edit to `docker-compose.yml`.

2. **🟠 DC-014 — Add `logging: driver: json-file + max-size/max-file` to every service.** GCP e2-medium boot disks are typically 10–20 GB. Without rotation, verbose Temporal logs fill the disk in hours under load. One YAML anchor (`x-logging`) added once, referenced everywhere.

3. **🟠 DC-022 — Bind backend port 8000 to `127.0.0.1`.** The backend API (`/docs`, `/openapi.json`, all data routes) must not be publicly reachable. Add `127.0.0.1:` prefix. Also delete the `ufw allow 8000/tcp` line from DEPLOY.md (INFRA-045).

4. **🟠 DC-013 — Prefix all dev overlay ports with `127.0.0.1:`.** Prevents accidental public exposure of Postgres/Redis/Temporal when an operator mistakenly includes `docker-compose.dev.yml` on the GCP VM.

5. **🟠 DC-002 — Set a default release tag, not `:latest`.** On GCP, `docker compose pull` with `:latest` is a silent rolling update that can break prod at any time.

---

*End of DEPLOY_COMPOSE.md.*
