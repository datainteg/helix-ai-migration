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

## Quick start (≈ 5 minutes)

```bash
# 1. Clone the repo
git clone https://github.com/<your-fork>/helix-ai-migration.git
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

```bash
# Allow only what the public needs.
ufw allow 22/tcp        # SSH
ufw allow 3000/tcp      # Frontend (or 80/443 if proxied)
ufw allow 8000/tcp      # Backend API
# Temporal UI: do NOT open to internet. Use SSH tunnel from your laptop:
#   ssh -L 8233:localhost:8233 user@server
# Then open http://localhost:8233 locally.
ufw enable
```

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
