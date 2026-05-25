#!/usr/bin/env bash
# Helix Migration — one-click setup.
#
# What this does:
#   1. Verifies Docker + Compose v2 are available.
#   2. Creates .env from .env.example if missing, then fills generated
#      secrets via scripts/generate-secrets.sh (idempotent — re-running
#      keeps existing values; pass --force to rotate).
#   3. Builds container images (backend / worker / frontend).
#   4. Brings the stack up in the background.
#   5. Runs alembic migrations inside the backend container.
#   6. Waits for /api/v1/readyz to return 200.
#   7. Prints URLs + first-admin onboarding instructions.
#
# Usage:
#   ./setup.sh                    # default — first-time install
#   ./setup.sh --rebuild          # force `docker compose build --no-cache`
#   ./setup.sh --rotate-secrets   # overwrite existing secrets in .env
#   ./setup.sh --down             # stop the stack (keeps volumes)
#   ./setup.sh --nuke             # stop + remove containers + volumes
#
# Requirements:
#   - Docker Engine 24+
#   - Docker Compose v2 (`docker compose ...`, not docker-compose)
#   - Bash 4+ (Linux/macOS/WSL)
#
# Hardware floor: 4 GB RAM, 2 vCPU, 8 GB disk for the runtime stack.

set -euo pipefail

# ── Colours (auto-disable when not a TTY) ────────────────────────────
if [ -t 1 ]; then
  C_RED=$'\033[31m'; C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'
  C_BLUE=$'\033[34m'; C_DIM=$'\033[2m'; C_BOLD=$'\033[1m'; C_RST=$'\033[0m'
else
  C_RED=""; C_GREEN=""; C_YELLOW=""; C_BLUE=""; C_DIM=""; C_BOLD=""; C_RST=""
fi

log()  { printf "%s%s%s %s\n" "$C_BLUE" "→" "$C_RST" "$*"; }
ok()   { printf "%s%s%s %s\n" "$C_GREEN" "✓" "$C_RST" "$*"; }
warn() { printf "%s%s%s %s\n" "$C_YELLOW" "!" "$C_RST" "$*"; }
err()  { printf "%s%s%s %s\n" "$C_RED" "✗" "$C_RST" "$*" >&2; }

# ── Arg parsing ──────────────────────────────────────────────────────
REBUILD=false
ROTATE_SECRETS=false
DOWN=false
NUKE=false

while [ $# -gt 0 ]; do
  case "$1" in
    --rebuild)         REBUILD=true ;;
    --rotate-secrets)  ROTATE_SECRETS=true ;;
    --down)            DOWN=true ;;
    --nuke)            NUKE=true ;;
    -h|--help)
      sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      err "Unknown flag: $1"
      exit 1
      ;;
  esac
  shift
done

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.build.yml)

# ── Stop/teardown shortcuts ──────────────────────────────────────────
if $DOWN; then
  log "Stopping the stack…"
  docker compose "${COMPOSE_FILES[@]}" down
  ok "Stopped. Volumes preserved."
  exit 0
fi

if $NUKE; then
  warn "About to remove containers AND persistent volumes (Postgres, Redis, artifacts)."
  read -r -p "Type 'nuke' to confirm: " confirm
  if [ "$confirm" != "nuke" ]; then
    err "Aborted."
    exit 1
  fi
  docker compose "${COMPOSE_FILES[@]}" down -v
  ok "Stack torn down. All data deleted."
  exit 0
fi

# ── 1. Preflight ─────────────────────────────────────────────────────
log "Checking Docker…"
if ! command -v docker >/dev/null 2>&1; then
  err "docker not found in PATH. Install Docker Desktop (Mac/Windows) or docker-ce (Linux)."
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  err "Docker Compose v2 plugin missing. Install with: apt install docker-compose-plugin (Linux) or upgrade Docker Desktop."
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  err "Docker daemon not running. Start Docker Desktop or 'sudo systemctl start docker'."
  exit 1
fi
ok "Docker $(docker --version | awk '{print $3}' | tr -d ',') + Compose $(docker compose version --short)."

# ── 2. .env + secrets ────────────────────────────────────────────────
log "Provisioning .env…"
if [ ! -f .env ]; then
  if [ ! -f .env.example ]; then
    err ".env.example missing — fork looks incomplete. Cannot proceed."
    exit 1
  fi
  cp .env.example .env
  ok "Created .env from .env.example."
else
  ok ".env already present — keeping existing values."
fi

GEN_FLAGS=()
if $ROTATE_SECRETS; then
  GEN_FLAGS+=(--force)
  warn "Rotating secrets — existing JWT tokens + audit chains will be invalidated."
fi

if [ -x scripts/generate-secrets.sh ]; then
  log "Filling secrets via scripts/generate-secrets.sh…"
  ./scripts/generate-secrets.sh "${GEN_FLAGS[@]}"
elif [ -f scripts/generate-secrets.sh ]; then
  log "Filling secrets via scripts/generate-secrets.sh (bash)…"
  bash scripts/generate-secrets.sh "${GEN_FLAGS[@]}"
else
  warn "scripts/generate-secrets.sh not found — secrets in .env must be set manually before continuing."
  exit 1
fi

# Confirm critical secrets are non-empty.
required_keys=(POSTGRES_PASSWORD JWT_SECRET_KEY ENCRYPTION_KEY AUDIT_HMAC_KEY)
missing=()
for k in "${required_keys[@]}"; do
  if ! grep -Eq "^${k}=.+" .env; then
    missing+=("$k")
  fi
done
if [ ${#missing[@]} -gt 0 ]; then
  err "Missing required env vars after secret generation: ${missing[*]}"
  exit 1
fi
ok "All required secrets present."

# ── 3. Build images ──────────────────────────────────────────────────
log "Building container images (this can take 5-10 min on first run)…"
build_args=()
if $REBUILD; then
  build_args+=(--no-cache --pull)
fi
docker compose "${COMPOSE_FILES[@]}" build "${build_args[@]}"
ok "Images built."

# ── 4. Start stack ───────────────────────────────────────────────────
log "Starting Postgres + Redis + Temporal…"
docker compose "${COMPOSE_FILES[@]}" up -d postgres redis temporal

log "Waiting for Postgres to accept connections…"
for i in $(seq 1 30); do
  if docker compose "${COMPOSE_FILES[@]}" exec -T postgres pg_isready -U "${POSTGRES_USER:-helix}" >/dev/null 2>&1; then
    ok "Postgres ready."
    break
  fi
  if [ "$i" -eq 30 ]; then
    err "Postgres did not become ready within 60s. Check: docker compose logs postgres"
    exit 1
  fi
  sleep 2
done

# ── 5. Migrations ────────────────────────────────────────────────────
log "Bringing up backend (will run alembic on startup)…"
docker compose "${COMPOSE_FILES[@]}" up -d backend worker frontend

log "Waiting for backend /api/v1/readyz (DB-gated)…"
backend_url="http://localhost:${BACKEND_HOST_PORT:-8000}/api/v1/readyz"
ready=false
for i in $(seq 1 60); do
  status=$(curl -s -o /dev/null -w "%{http_code}" "$backend_url" 2>/dev/null || echo "000")
  if [ "$status" = "200" ]; then
    ready=true
    break
  fi
  sleep 2
done
if ! $ready; then
  err "Backend did not pass /readyz within 120s. Tail logs:"
  err "  docker compose logs --tail=80 backend"
  exit 1
fi
ok "Backend ready."

# ── 6. Friendly summary ──────────────────────────────────────────────
frontend_port="${FRONTEND_HOST_PORT:-3000}"
backend_port="${BACKEND_HOST_PORT:-8000}"

cat <<EOF

${C_BOLD}${C_GREEN}Helix is up.${C_RST}

  ${C_BOLD}Frontend${C_RST}   http://localhost:${frontend_port}
  ${C_BOLD}Backend${C_RST}    http://localhost:${backend_port}
  ${C_BOLD}OpenAPI${C_RST}    http://localhost:${backend_port}/docs
  ${C_BOLD}Health${C_RST}     http://localhost:${backend_port}/api/v1/health
  ${C_BOLD}Ready${C_RST}      http://localhost:${backend_port}/api/v1/readyz
  ${C_BOLD}Metrics${C_RST}    http://localhost:${backend_port}/metrics

${C_DIM}# First-time setup — open the frontend and walk through the wizard:${C_RST}
${C_DIM}#   http://localhost:${frontend_port}/setup/first-admin${C_RST}

${C_DIM}# Common ops:${C_RST}
${C_DIM}#   docker compose ${COMPOSE_FILES[*]} logs -f backend worker${C_RST}
${C_DIM}#   docker compose ${COMPOSE_FILES[*]} ps${C_RST}
${C_DIM}#   ./setup.sh --down            # stop, keep data${C_RST}
${C_DIM}#   ./setup.sh --rotate-secrets  # rotate JWT/encryption keys${C_RST}
${C_DIM}#   docker compose --profile debug up -d temporal-ui  # opt-in Temporal UI on 127.0.0.1:8233${C_RST}

EOF
