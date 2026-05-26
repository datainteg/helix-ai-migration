# Helix Migration — Deployment Guide

Helix runs as a single Docker Compose stack. All services share one bridge
network; only `backend`, `frontend`, and `temporal-ui` are reachable from
outside the host.

## Prerequisites

| Requirement | Minimum | Notes |
|-------------|---------|-------|
| Docker Engine | 24.0+ | `docker --version` |
| Docker Compose | v2 | `docker compose version` |
| CPU | 2 cores | 4 recommended for production |
| RAM | 4 GB | 8 GB recommended; LangGraph + Temporal each want ~1 GB |
| Disk | 20 GB | Postgres data + artifact storage grow over time |
| OS | Linux x86_64 | Compose also works on macOS / Windows for local dev |

You do NOT need: nginx, a managed TLS cert, Kubernetes, or a cloud-specific
runtime. Helix is designed for `docker compose up` on a single host. Operators
who want TLS, load balancing, or multi-host should add their own reverse
proxy (Caddy, Traefik, etc.) in front of the `frontend` + `backend` containers.

---

## One-click install (recommended)

```bash
git clone https://github.com/datainteg/helix-ai-migration.git
cd helix-ai-migration
./setup.sh           # Linux / macOS / WSL
# or:
.\setup.ps1          # Windows PowerShell
```

`setup.sh` / `setup.ps1`:

1. Verifies Docker + Compose v2 are installed and the daemon is running.
2. Copies `.env.example` → `.env` (if missing) and fills generated secrets.
3. Builds the backend / worker / frontend images.
4. Starts Postgres + Redis + Temporal, waits for Postgres readiness.
5. Brings up backend (alembic runs on container start) + worker + frontend.
6. Polls `/api/v1/readyz` (DB-gated) until the backend is serving traffic.
7. Prints URLs + the first-admin wizard link.

Useful flags:

```bash
./setup.sh --rebuild           # docker compose build --no-cache
./setup.sh --rotate-secrets    # rotate JWT / ENCRYPTION / AUDIT_HMAC keys
./setup.sh --down              # stop the stack, keep volumes
./setup.sh --nuke              # stop AND delete volumes (Postgres, artifacts)
```

After it finishes, open `http://localhost:3000/setup/first-admin` and follow the wizard.

---

## Manual install (≈ 5 minutes)

```bash
# 1. Clone the repo
git clone https://github.com/datainteg/helix-ai-migration.git
cd helix-ai-migration

# 2. Generate strong secrets into .env
./scripts/generate-secrets.sh          # Linux / macOS / WSL
# or:
.\scripts\generate-secrets.ps1         # Windows PowerShell

# 3. Edit .env — set NEXT_PUBLIC_API_URL + CORS_ORIGINS to match your domain.
${EDITOR:-nano} .env

# 4a. EITHER build images locally (one-time, ~5 min):
docker compose -f docker-compose.yml -f docker-compose.build.yml build

# 4b. OR pull pre-built images (when you've configured HELIX_IMAGE_PREFIX):
docker compose pull

# 5. Start the stack
docker compose up -d

# 6. Apply DB migrations (runs alembic + creates tables)
docker compose exec backend alembic upgrade head

# 7. Open the UI
open http://localhost:3000    # macOS
# or just navigate to that URL in any browser
```

First-run flow inside the UI:
1. `/setup/first-admin` — create the initial admin + organization.
2. `/admin/llm-settings` — add an LLM provider (OpenAI, Anthropic, Gemini, DeepSeek, OpenRouter, local Ollama, or any OpenAI-compatible).
3. `/admin/agent-mapping` — map the 6 BMAD agents to the provider(s) you configured.
4. `/projects/new` — create a migration project, add a requirement, click "Generate Plan".
5. `/agents` — watch the 13-node BMAD pipeline execute live.

---

## Services + Ports

| Service | Internal address | Host port | Public-facing? |
|---------|------------------|-----------|----------------|
| `frontend` | frontend:3000 | `${FRONTEND_HOST_PORT:-3000}` | Yes |
| `backend` | backend:8000 | `${BACKEND_HOST_PORT:-8000}` | Yes (your domain ⇒ this) |
| `temporal-ui` | temporal-ui:8080 | `${TEMPORAL_UI_HOST_PORT:-8233}` | **Operator-only** — firewall it |
| `postgres` | postgres:5432 | — | No (internal) |
| `redis` | redis:6379 | — | No (internal) |
| `temporal` | temporal:7233 | — | No (internal) |

> Override any host port via env before `docker compose up`, e.g.
> `BACKEND_HOST_PORT=8001 docker compose up -d`.

### Firewall recommendation

When a reverse proxy (Caddy / nginx) terminates TLS on the same host, the
backend (port 8000) and frontend (port 3000) should be bound to loopback only
so the proxy can reach them but the public internet cannot.

```bash
# Allow only what the public needs.
ufw allow 22/tcp        # SSH
ufw allow 80/tcp        # HTTP (ACME challenge + redirect to HTTPS)
ufw allow 443/tcp       # HTTPS (Caddy / nginx)
# DO NOT open 3000 or 8000 directly — the reverse proxy handles them
#   over loopback (127.0.0.1).
# Temporal UI: do NOT open to internet. Use SSH tunnel from your laptop:
#   ssh -L 8233:localhost:8233 user@server
# Then open http://localhost:8233 locally.
ufw enable
```

> **Before wave-2 (F2 compose change):** docker-compose.yml bound backend and
> frontend to `0.0.0.0` by default. Wave-2 changed the default bind to
> `127.0.0.1`. If you are running a pre-wave-2 stack, **do not** open port
> 8000 to the public internet via a firewall rule — it exposes the full API,
> admin endpoints, OpenAPI docs, and Prometheus metrics.

---

## Environment variables

`scripts/generate-secrets.sh` fills these for you:

| Variable | Why | Generator |
|----------|-----|-----------|
| `POSTGRES_PASSWORD` | DB auth | 32-char hex |
| `APP_SECRET_KEY` | App signing | 64-char hex |
| `JWT_SECRET_KEY` | JWT signing | 64-char hex |
| `ENCRYPTION_KEY` | LLM key encryption (Fernet) | 44-char base64 |
| `TEMPORAL_UI_PASSWORD` | Optional UI auth | 24-char hex |

You set these manually:

| Variable | What |
|----------|------|
| `NEXT_PUBLIC_API_URL` | What the browser uses to call the backend. Baked at build time. Local: `http://localhost:8000`. Production: `https://api.yourdomain.com`. |
| `CORS_ORIGINS` | JSON array of allowed frontend origins. Production: `["https://yourdomain.com"]`. |
| `FRONTEND_URL` | Used in invitation + password-reset emails. |
| `SMTP_*` | Optional — required only for email invitations. |

See [.env.example](.env.example) for the full list with comments.

### DATABASE_URL driver note (asyncpg vs psycopg2)

`DATABASE_URL` should always use the `postgresql://` scheme (psycopg2 driver).
The async SQLAlchemy engine in the backend rewrites this automatically to
`postgresql+asyncpg://` for async contexts (background tasks, SSE streams).
Sync paths (Alembic migrations, wrapped sync DB work) continue using psycopg2.

**Do not manually set `DATABASE_URL` to `postgresql+asyncpg://`** — the
application rewrites it at startup and a double-prefix will cause connection
errors. See `backend/app/db/session.py` lines 8–10 for the rewrite logic.

---

## Image strategy

`docker-compose.yml` uses env-driven image names so the same file works for
local builds AND for pulling pre-built images from a registry:

```bash
# Local builds (default — images named `helix/backend:latest` etc.)
docker compose -f docker-compose.yml -f docker-compose.build.yml build

# Pull from your registry
export HELIX_IMAGE_PREFIX=ghcr.io/your-org
export HELIX_IMAGE_TAG=v0.5.0
docker compose pull
docker compose up -d
```

Publishing to GHCR (one-time setup):

```bash
docker login ghcr.io
docker compose -f docker-compose.yml -f docker-compose.build.yml build
docker push ghcr.io/your-org/backend:v0.5.0
docker push ghcr.io/your-org/worker:v0.5.0
docker push ghcr.io/your-org/frontend:v0.5.0
```

---

## Day-2 ops

### Logs

```bash
docker compose logs -f backend           # one service
docker compose logs -f --tail=200        # all services, last 200 lines
```

### Restart a single service

```bash
docker compose restart worker
```

### Apply migrations after upgrading

```bash
docker compose pull            # or rebuild
docker compose up -d
docker compose exec backend alembic upgrade head
```

> **Note:** on a fresh install the backend container runs `alembic upgrade
> head` automatically on boot (see `backend/Dockerfile`). The manual step
> above is only needed when upgrading an existing installation that is already
> running.

#### Wave-1 / wave-2 / wave-3 migration list

All migrations are applied automatically by `alembic upgrade head`. The table
below is a reference for operators who need to audit what changed between
versions.

| Revision | Wave | Description |
|----------|------|-------------|
| `eadec18c9cfc` | wave-1 | `workflow_steps.parsed_output` → JSONB (DI fix) |
| `8f881cfc333e` | wave-1 | Identity UUID columns → String(36) (destructive on existing data — take a Postgres backup first) |
| `p7q8r9s0t1u2` | wave-1 | Missing indexes for performance (perf fix) |
| `2af2b45b4051` | wave-2 | `org_data_encryption_keys.organization_id` UNIQUE → partial UNIQUE on `(organization_id) WHERE is_active=true`. Required for DEK rotation (DI-C1). Safe to rerun. |
| `q8r9s0t1u2v3` | wave-2 | Encrypts plaintext secrets in `llm_providers.extra_config` (Bedrock `aws_secret_access_key`, Vertex `service_account_json`, Azure `client_secret`). Idempotent; skips already-encrypted rows (SEC-010). |

If upgrading from wave-1 to wave-2 on a live database, take a Postgres backup
**before** running `alembic upgrade head` — `8f881cfc333e` is destructive on
existing identity columns and cannot be auto-reversed.

#### Post-upgrade verification

After `alembic upgrade head` succeeds:

1. **Confirm no orphaned workflows:** check for workflows stuck in
   `awaiting_approval` and approve or reject them before running the upgrade
   if you need a clean cutover.

2. **DEK health check (wave-2+):**
   ```sql
   SELECT COUNT(DISTINCT organization_id)
   FROM org_data_encryption_keys
   WHERE is_active = true;
   -- should equal the number of organizations
   ```

3. **Extra-config encryption check (wave-2+):**
   ```sql
   SELECT COUNT(*) FROM llm_providers WHERE extra_config IS NOT NULL;
   -- if > 0, verify rows were re-encrypted by q8r9s0t1u2v3
   ```

4. **KEK rotation (if required by your security policy):**
   ```bash
   docker compose exec backend python -m app.cli.rotate rotate-keks --confirm
   ```

5. **Smoke test list:**
   - `GET /api/v1/readyz` → `{"status": "ok"}`
   - `GET /api/v1/health` → `{"status": "ok"}`
   - `POST /api/v1/auth/login` with a known account → 200
   - `GET /api/v1/projects?limit=1` → pagination envelope `{items, total, limit, offset}`
   - Temporal UI reachable on localhost:8233 via SSH tunnel

### Postgres backup

```bash
# Manual dump (run from host)
docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" \
  | gzip > backups/helix-$(date +%F).sql.gz

# Restore
gunzip -c backups/helix-2026-05-25.sql.gz \
  | docker compose exec -T postgres psql -U "$POSTGRES_USER" "$POSTGRES_DB"
```

Schedule via host cron:

```cron
0 3 * * * cd /opt/helix && docker compose exec -T postgres pg_dump -U helix helix_metadata | gzip > backups/helix-$(date +\%F).sql.gz
```

### Artifact backup

BMAD writes markdown artifacts to the `helix_artifacts` volume:

```bash
docker run --rm \
  -v helix-ai-migration_helix_artifacts:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/artifacts-$(date +%F).tgz -C /data .
```

### Reset everything (DESTRUCTIVE — wipes DB + artifacts)

```bash
docker compose down -v        # -v also drops volumes
```

---

## Data persistence

| Volume | Holds | Survives `docker compose down`? | Survives `down -v`? |
|--------|-------|----------------------------------|---------------------|
| `helix_postgres_data` | Postgres DB | Yes | **No** |
| `helix_artifacts` | BMAD markdown artifacts | Yes | **No** |

For long-term durability point these to host-mounted paths (or to an external
storage driver) in a compose override file:

```yaml
# docker-compose.override.yml
volumes:
  helix_postgres_data:
    driver: local
    driver_opts:
      type: none
      device: /srv/helix/postgres
      o: bind
  helix_artifacts:
    driver: local
    driver_opts:
      type: none
      device: /srv/helix/artifacts
      o: bind
```

---

## Resource sizing

Defaults in `docker-compose.yml` (per-service memory limit):

| Service | Limit | Rationale |
|---------|-------|-----------|
| postgres | 1 GB | scales with project count |
| redis | 256 MB | session + cache only |
| temporal | 1 GB | workflow history |
| temporal-ui | 256 MB | thin UI |
| backend | 1 GB | FastAPI + SQLAlchemy |
| worker | 1 GB | LangGraph + LLM clients |
| frontend | 512 MB | Next.js standalone |

Adjust under `deploy.resources.limits` per service if needed.

---

## Common cloud targets

These are not endorsements — just notes on how the same compose file lands
on each platform.

| Platform | Notes |
|----------|-------|
| **Bare VM** (DigitalOcean Droplet, Hetzner, EC2) | Install Docker + compose. Clone repo. Run quick-start. Add Caddy/Traefik for TLS. |
| **Docker-friendly PaaS** (Render, Railway, Fly.io) | Each service deploys separately. You'll need to publish images to a registry. Use their managed Postgres + Redis instead of the bundled containers — point `DATABASE_URL` + `REDIS_URL` at the managed instance. |
| **Kubernetes** | Use `docker-compose.yml` as a starting point. Convert with `kompose` or write Helm chart. Postgres + Redis + Temporal as separate StatefulSets. |
| **Cloud Run / App Runner** | One container per service. Backend + worker + frontend as separate services. Bring your own Postgres + Redis + Temporal Cloud. |

---

## GCP one-VM deploy

Recommended instance: `e2-standard-2` (2 vCPU, 8 GB RAM). The documented
4 GB floor is too tight; the Compose stack consumes ~4.8 GB before OS
overhead and will OOM-kill the worker under load on an `e2-medium`.

### Step-by-step

1. **Reserve a static external IP** (required — ephemeral IPs break
   `NEXT_PUBLIC_API_URL` and TLS certs on VM restart):
   ```bash
   gcloud compute addresses create helix-vm-ip --region=us-central1
   gcloud compute instances add-access-config INSTANCE_NAME \
     --access-config-name="External NAT" --address=STATIC_IP
   ```

2. **Create a DNS A record:** `helix.example.com → STATIC_IP` (TTL 300).
   Wait for propagation (`dig helix.example.com`) before running `setup.sh`.

3. **GCP firewall rules** (tag your VM with `helix-vm` at creation):
   ```bash
   # Allow HTTPS (TLS termination by Caddy on the VM)
   gcloud compute firewall-rules create helix-allow-https \
     --direction=INGRESS --action=ALLOW --rules=tcp:443 \
     --source-ranges=0.0.0.0/0 --target-tags=helix-vm

   # Allow HTTP (ACME challenge + redirect)
   gcloud compute firewall-rules create helix-allow-http \
     --direction=INGRESS --action=ALLOW --rules=tcp:80 \
     --source-ranges=0.0.0.0/0 --target-tags=helix-vm

   # SSH via IAP (no public port required)
   gcloud compute firewall-rules create helix-allow-iap-ssh \
     --direction=INGRESS --action=ALLOW --rules=tcp:22 \
     --source-ranges=35.235.240.0/20 --target-tags=helix-vm
   # DO NOT open 3000, 5432, 6379, 7233, 8000, or 8233.
   ```

4. **Set `.env` before building** (NEXT_PUBLIC_API_URL is baked at build time):
   ```bash
   NEXT_PUBLIC_API_URL=https://helix.example.com
   CORS_ORIGINS=["https://helix.example.com"]
   FRONTEND_URL=https://helix.example.com
   PUBLIC_HOSTNAME=helix.example.com
   CADDY_ADMIN_EMAIL=ops@example.com
   ```

5. **Run setup.sh:**
   ```bash
   ./setup.sh
   ```

6. **Bootstrap the first admin** (headless — no browser needed):
   ```bash
   pip install helix-cli
   helix admin bootstrap \
     --api https://helix.example.com \
     --email ops@example.com \
     --org-name "Acme Corp" \
     --accept-tos
   # prompts for password, exits 0 on success
   ```

### Caddy TLS (recommended reverse proxy)

Caddy auto-obtains Let's Encrypt certs, handles SSE buffering automatically,
and requires no extra config for `text/event-stream`. Add a `caddy` service to
`docker-compose.yml` and create `deploy/caddy/Caddyfile`:

```caddyfile
{
    email {$CADDY_ADMIN_EMAIL}
}

{$PUBLIC_HOSTNAME} {
    handle /api/* {
        reverse_proxy backend:8000 {
            header_up Host {http.request.host}
            header_up X-Forwarded-Proto https
            header_up X-Real-IP {http.request.remote.host}
        }
    }
    handle /docs* { reverse_proxy backend:8000 }
    handle /metrics { respond 403 }
    handle /* {
        reverse_proxy frontend:3000 {
            header_up Host {http.request.host}
        }
    }
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options nosniff
        X-Frame-Options DENY
        Referrer-Policy strict-origin-when-cross-origin
    }
}
```

Add to `docker-compose.yml` services:

```yaml
  caddy:
    image: caddy:2.8-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp"
    environment:
      PUBLIC_HOSTNAME: ${PUBLIC_HOSTNAME:?required}
      CADDY_ADMIN_EMAIL: ${CADDY_ADMIN_EMAIL:?required}
    volumes:
      - ./deploy/caddy/Caddyfile:/etc/caddy/Caddyfile:ro
      - helix_caddy_data:/data
      - helix_caddy_config:/config
    depends_on:
      backend:
        condition: service_healthy
      frontend:
        condition: service_started
    networks:
      - helix-network
    deploy:
      resources:
        limits:
          memory: 128M
```

Also change backend and frontend port bindings to loopback-only:

```yaml
# backend
ports:
  - "${BACKEND_BIND:-127.0.0.1}:${BACKEND_HOST_PORT:-8000}:8000"

# frontend
ports:
  - "${FRONTEND_BIND:-127.0.0.1}:${FRONTEND_HOST_PORT:-3000}:3000"
```

After adding Caddy, verify: `curl -I https://helix.example.com/api/v1/readyz`
should return `200 OK` over HTTPS.

### GCP Docker network MTU

GCP VPC default MTU is 1460 (not 1500). Add to `docker-compose.yml` to prevent
silent packet fragmentation on large LLM streaming responses:

```yaml
networks:
  helix-network:
    driver: bridge
    driver_opts:
      com.docker.network.driver.mtu: "1460"
```

---

## Updating Helix

```bash
git pull
./scripts/generate-secrets.sh        # safely fills any new required vars
docker compose pull                  # or build with overlay
docker compose up -d
docker compose exec backend alembic upgrade head
```

---

## Troubleshooting

**`POSTGRES_PASSWORD is required` on `docker compose up`** — run
`./scripts/generate-secrets.sh` first.

**Backend exits with `JWT_SECRET_KEY=change_me is unsafe`** — the secrets
script wasn't run. Either run it or set the value manually in `.env`.

**Workflow stuck at `awaiting_approval`** — the BMAD pipeline paused at the
human approval gate. Approve from `/agents` in the UI or send the Temporal
signal directly.

**Worker container restarts in a loop** — check `docker compose logs worker`.
Most common cause: Temporal not yet healthy when worker started. Worker
restarts automatically; wait ~30 s.

**`docker compose pull` says image not found** — set
`HELIX_IMAGE_PREFIX=ghcr.io/<your-org>` and re-pull, OR build locally with
the build overlay.

**Frontend shows "Failed to fetch"** — `NEXT_PUBLIC_API_URL` was baked into
the frontend image at build time and doesn't match where backend is now
reachable. Rebuild the frontend image with the correct `NEXT_PUBLIC_API_URL`
build arg.
