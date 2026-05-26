#!/usr/bin/env bash
# Helix Migration — one-click setup.
#
# What this does:
#   0. (NEW) If --install-docker (or auto on fresh VM), bootstraps Docker
#      Engine + Compose v2 via the official distro-aware installer.
#   1. Verifies Docker + Compose v2 are available.
#   2. Creates .env from .env.example if missing, then fills generated
#      secrets via scripts/generate-secrets.sh (idempotent — re-running
#      keeps existing values; pass --rotate-secrets + --force +
#      --confirm-data-loss to rotate).
#   3. Detects the public IP (GCE metadata, then AWS IMDS) so the frontend
#      bundle is built with the correct NEXT_PUBLIC_API_URL.
#   4. Builds container images (backend / worker / frontend).
#   5. Brings the stack up in the background.
#   6. Runs alembic migrations inside the backend container.
#   7. Waits for /api/v1/readyz to return 200.
#   8. Prints URLs + first-admin onboarding instructions.
#
# Usage:
#   ./setup.sh                            # default — first-time install
#   ./setup.sh --non-interactive          # never prompt; accept defaults
#   ./setup.sh --install-docker           # force docker bootstrap
#   ./setup.sh --skip-docker-install      # operator manages docker out-of-band
#   ./setup.sh --domain helix.example.com # public hostname for TLS deploys
#   ./setup.sh --admin-email X --admin-password Y   # pre-seed first admin
#   ./setup.sh --rebuild                  # docker compose build --no-cache
#   ./setup.sh --rotate-secrets --force --confirm-data-loss
#   ./setup.sh --down                     # stop the stack (keeps volumes)
#   ./setup.sh --nuke                     # stop + remove containers + volumes
#
# curl|bash flow:
#   curl -fsSL https://raw.githubusercontent.com/datainteg/helix-ai-migration/main/setup.sh \
#     | sudo bash -s -- --non-interactive --domain helix.example.com
#
# Requirements:
#   - Docker Engine 24+ (auto-installed on Ubuntu/Debian/Fedora/RHEL/Alpine/Arch)
#   - Docker Compose v2 (`docker compose ...`)
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

REPO_URL="https://github.com/datainteg/helix-ai-migration"

# ── Arg parsing ──────────────────────────────────────────────────────
REBUILD=false
ROTATE_SECRETS=false
ROTATE_FORCE=false
CONFIRM_DATA_LOSS=false
DOWN=false
NUKE=false
NON_INTERACTIVE=${HELIX_NON_INTERACTIVE:-false}
INSTALL_DOCKER=auto              # auto | force | skip
DOMAIN=""
ADMIN_EMAIL=""
ADMIN_PASSWORD=""

while [ $# -gt 0 ]; do
  case "$1" in
    --rebuild)              REBUILD=true ;;
    --rotate-secrets)       ROTATE_SECRETS=true ;;
    --force)                ROTATE_FORCE=true ;;
    --confirm-data-loss)    CONFIRM_DATA_LOSS=true ;;
    --down)                 DOWN=true ;;
    --nuke)                 NUKE=true ;;
    --non-interactive|--yes) NON_INTERACTIVE=true ;;
    --install-docker)       INSTALL_DOCKER=force ;;
    --skip-docker-install)  INSTALL_DOCKER=skip ;;
    --domain)               DOMAIN="${2:-}"; shift ;;
    --domain=*)             DOMAIN="${1#*=}" ;;
    --admin-email)          ADMIN_EMAIL="${2:-}"; shift ;;
    --admin-email=*)        ADMIN_EMAIL="${1#*=}" ;;
    --admin-password)       ADMIN_PASSWORD="${2:-}"; shift ;;
    --admin-password=*)     ADMIN_PASSWORD="${1#*=}" ;;
    -h|--help)
      sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      err "Unknown flag: $1"
      err "Run './setup.sh --help' for usage."
      exit 1
      ;;
  esac
  shift
done

# If invoked as `curl|bash`, $0 is bash — fall back to CWD.
if [ -f "$0" ] 2>/dev/null; then
  ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
else
  ROOT_DIR="$(pwd)"
fi
cd "$ROOT_DIR"

COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.build.yml)

# Caddy reverse-proxy is gated behind the `tls` profile in docker-compose.yml.
# Auto-enable it when --domain is set (operator wants public TLS).
COMPOSE_PROFILES=()
if [ -n "${DOMAIN:-}" ]; then
  COMPOSE_PROFILES=(--profile tls)
fi

confirm() {
  # Usage: confirm "message" "expected"
  if $NON_INTERACTIVE; then
    return 0
  fi
  local prompt="$1" expected="$2" reply=""
  read -r -p "$prompt" reply || return 1
  [ "$reply" = "$expected" ]
}

# ── Stop/teardown shortcuts ──────────────────────────────────────────
if $DOWN; then
  log "Stopping the stack…"
  docker compose "${COMPOSE_FILES[@]}" "${COMPOSE_PROFILES[@]}" down
  ok "Stopped. Volumes preserved."
  exit 0
fi

if $NUKE; then
  warn "About to remove containers AND persistent volumes (Postgres, Redis, artifacts)."
  if ! $NON_INTERACTIVE; then
    if ! confirm "Type 'nuke' to confirm: " "nuke"; then
      err "Aborted."
      exit 1
    fi
  else
    warn "--non-interactive set; proceeding without confirmation."
  fi
  docker compose "${COMPOSE_FILES[@]}" "${COMPOSE_PROFILES[@]}" down -v
  ok "Stack torn down. All data deleted."
  exit 0
fi

# ── Rotate-secrets safety gate (DSETUP-010 / B-8) ────────────────────
if $ROTATE_SECRETS; then
  if ! $ROTATE_FORCE || ! $CONFIRM_DATA_LOSS; then
    err "--rotate-secrets refused without both --force AND --confirm-data-loss."
    err ""
    err "  Rotating ENCRYPTION_KEY invalidates every encrypted LLM API key,"
    err "  every connector credential, and breaks the audit-log HMAC chain."
    err "  Wave-3 will ship a re-encryption migration; until then, rotation is"
    err "  destructive."
    err ""
    err "  If you accept the data loss, re-run with:"
    err "    ./setup.sh --rotate-secrets --force --confirm-data-loss"
    exit 2
  fi
  warn "Rotating secrets — encrypted LLM keys + connector creds + audit chain will be invalidated."
fi

# ── 0. Docker installer (DSETUP-001) ─────────────────────────────────
detect_distro() {
  if [ -r /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    printf '%s' "${ID:-unknown}"
  else
    printf 'unknown'
  fi
}

iptables_nft_check() {
  # Ubuntu 24 LTS gotcha (DSETUP-iptables-nft).
  [ -L /usr/sbin/iptables ] || return 0
  local target
  target=$(readlink -f /usr/sbin/iptables 2>/dev/null || true)
  case "$target" in
    *iptables-legacy*)
      warn "iptables is in legacy mode; Docker on Ubuntu 24 expects nftables."
      if command -v update-alternatives >/dev/null 2>&1; then
        if $NON_INTERACTIVE || confirm "Switch iptables to nftables now? [y/N]: " "y"; then
          sudo update-alternatives --set iptables /usr/sbin/iptables-nft || \
            warn "update-alternatives failed; container networking may misbehave."
          ok "iptables -> nftables backend."
        else
          warn "Skipped. If Docker bridge fails, run: sudo update-alternatives --set iptables /usr/sbin/iptables-nft"
        fi
      fi
      ;;
  esac
}

install_docker() {
  local distro="$1"
  log "Installing Docker Engine + Compose v2 for distro: ${distro}"
  local sudo_cmd=""
  if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1; then
      sudo_cmd="sudo"
    else
      err "Not root and sudo unavailable. Re-run as root or install sudo."
      exit 1
    fi
  fi
  case "$distro" in
    ubuntu|debian|raspbian|linuxmint|pop)
      # Official Docker convenience installer covers Ubuntu/Debian incl. 24.04.
      curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
      DEBIAN_FRONTEND=noninteractive $sudo_cmd sh /tmp/get-docker.sh
      rm -f /tmp/get-docker.sh
      ;;
    fedora|rhel|centos|rocky|almalinux|ol)
      curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
      $sudo_cmd sh /tmp/get-docker.sh
      rm -f /tmp/get-docker.sh
      ;;
    alpine)
      $sudo_cmd apk add --no-cache docker docker-cli-compose
      $sudo_cmd rc-update add docker default || true
      $sudo_cmd service docker start || true
      ;;
    arch|manjaro|endeavouros)
      $sudo_cmd pacman -Sy --noconfirm docker docker-compose
      $sudo_cmd systemctl enable --now docker
      ;;
    *)
      err "Unknown / unsupported distro: ${distro}"
      err "Install Docker manually following the official docs:"
      err "  https://docs.docker.com/engine/install/"
      err "Then re-run: ./setup.sh --skip-docker-install"
      exit 1
      ;;
  esac
  # Ensure daemon up.
  if command -v systemctl >/dev/null 2>&1; then
    $sudo_cmd systemctl enable --now docker 2>/dev/null || true
  fi
  ok "Docker installed."
  # Add invoking user to the docker group when not root.
  if [ "$(id -u)" -ne 0 ] && ! id -nG "$USER" 2>/dev/null | grep -qw docker; then
    $sudo_cmd usermod -aG docker "$USER" || true
    warn "Added $USER to the docker group. You may need to log out + back in."
    warn "If subsequent docker calls fail, re-run setup.sh after re-login (or under sudo)."
  fi
}

case "$INSTALL_DOCKER" in
  skip)
    : ;;
  force)
    iptables_nft_check
    install_docker "$(detect_distro)"
    ;;
  auto)
    if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
      iptables_nft_check
      install_docker "$(detect_distro)"
    fi
    ;;
esac

# ── 1. Preflight ─────────────────────────────────────────────────────
log "Checking Docker…"
if ! command -v docker >/dev/null 2>&1; then
  err "docker still not found after install attempt."
  err "Install manually: https://docs.docker.com/engine/install/  then re-run with --skip-docker-install"
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  err "Docker Compose v2 plugin missing."
  err "Ubuntu/Debian: sudo apt install docker-compose-plugin"
  err "Fedora/RHEL:   sudo dnf install docker-compose-plugin"
  err "Or run: ./setup.sh --install-docker"
  exit 1
fi
if ! docker info >/dev/null 2>/tmp/helix-docker-info.err; then
  if grep -q "permission denied" /tmp/helix-docker-info.err 2>/dev/null; then
    err "Cannot connect to the Docker socket — your user isn't in the docker group."
    err "  Fix: sudo usermod -aG docker \"\$USER\" && newgrp docker  (then re-login)"
  elif grep -q "Cannot connect to the Docker daemon" /tmp/helix-docker-info.err 2>/dev/null; then
    err "Docker daemon is not running. Start it: sudo systemctl start docker"
  else
    err "Docker is unhealthy:"
    cat /tmp/helix-docker-info.err >&2
  fi
  exit 1
fi
ok "Docker $(docker --version | awk '{print $3}' | tr -d ',') + Compose $(docker compose version --short)."

# Hardware + port preflight.
if [ -x scripts/preflight.sh ]; then
  log "Running hardware + port preflight…"
  bash scripts/preflight.sh || {
    err "Preflight failed. Address the warnings above and re-run."
    exit 1
  }
fi

# ── 2. .env + secrets ────────────────────────────────────────────────
log "Provisioning .env…"
if [ ! -f .env ]; then
  if [ ! -f .env.example ]; then
    err ".env.example missing — fork looks incomplete. Cannot proceed."
    err "Clone the canonical repo: ${REPO_URL}"
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
fi

if [ -x scripts/generate-secrets.sh ]; then
  log "Filling secrets via scripts/generate-secrets.sh…"
  ./scripts/generate-secrets.sh "${GEN_FLAGS[@]}"
elif [ -f scripts/generate-secrets.sh ]; then
  log "Filling secrets via scripts/generate-secrets.sh (bash)…"
  bash scripts/generate-secrets.sh "${GEN_FLAGS[@]}"
else
  err "scripts/generate-secrets.sh not found — secrets in .env must be set manually before continuing."
  exit 1
fi

# Lock down .env permissions.
chmod 600 .env 2>/dev/null || true

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

# Source .env so subsequent commands use operator-configured ports/users
# (DSETUP-007). `set -a` exports every assignment in the file.
set -a
# shellcheck disable=SC1091
. ./.env
set +a

# ── 2b. Public-URL / IP detection (DSETUP-028) ───────────────────────
detect_public_ip() {
  local ip=""
  # GCE metadata server (preferred — works on every GCP VM).
  ip=$(curl -fsSL --connect-timeout 2 \
        -H 'Metadata-Flavor: Google' \
        http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip \
        2>/dev/null || true)
  if [ -n "$ip" ]; then
    printf '%s' "$ip"
    return 0
  fi
  # AWS IMDSv2.
  local token
  token=$(curl -fsSL --connect-timeout 2 \
            -X PUT "http://169.254.169.254/latest/api/token" \
            -H "X-aws-ec2-metadata-token-ttl-seconds: 60" \
            2>/dev/null || true)
  if [ -n "$token" ]; then
    ip=$(curl -fsSL --connect-timeout 2 \
          -H "X-aws-ec2-metadata-token: $token" \
          http://169.254.169.254/latest/meta-data/public-ipv4 \
          2>/dev/null || true)
    if [ -n "$ip" ]; then
      printf '%s' "$ip"
      return 0
    fi
  fi
  # AWS IMDSv1 fallback.
  ip=$(curl -fsSL --connect-timeout 2 \
        http://169.254.169.254/latest/meta-data/public-ipv4 \
        2>/dev/null || true)
  if [ -n "$ip" ]; then
    printf '%s' "$ip"
    return 0
  fi
  return 1
}

PUBLIC_HOST=""
if [ -n "$DOMAIN" ]; then
  PUBLIC_HOST="$DOMAIN"
  log "Using --domain ${DOMAIN} as the public host."
  # Persist for downstream tooling.
  if grep -q '^HELIX_PUBLIC_DOMAIN=' .env; then
    sed -i.bak "s|^HELIX_PUBLIC_DOMAIN=.*|HELIX_PUBLIC_DOMAIN=${DOMAIN}|" .env && rm -f .env.bak
  else
    printf '\nHELIX_PUBLIC_DOMAIN=%s\n' "$DOMAIN" >> .env
  fi
else
  if detected_ip=$(detect_public_ip); then
    PUBLIC_HOST="$detected_ip"
    log "Detected public IP from cloud metadata: ${detected_ip}"
  else
    PUBLIC_HOST="localhost"
    log "No cloud metadata server reachable — defaulting NEXT_PUBLIC_API_URL to localhost."
  fi
fi

BACKEND_PORT_VAL="${BACKEND_HOST_PORT:-8000}"
if [ -n "$DOMAIN" ]; then
  # TLS deploy: assume the reverse proxy terminates 443 and proxies /api/*
  NEXT_PUBLIC_API_URL_VAL="https://${DOMAIN}"
else
  NEXT_PUBLIC_API_URL_VAL="http://${PUBLIC_HOST}:${BACKEND_PORT_VAL}"
fi
log "NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL_VAL}"
if grep -q '^NEXT_PUBLIC_API_URL=' .env; then
  sed -i.bak "s|^NEXT_PUBLIC_API_URL=.*|NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL_VAL}|" .env && rm -f .env.bak
else
  printf '\nNEXT_PUBLIC_API_URL=%s\n' "$NEXT_PUBLIC_API_URL_VAL" >> .env
fi
export NEXT_PUBLIC_API_URL="$NEXT_PUBLIC_API_URL_VAL"

# ── 2c. Pre-seed first-admin credentials (consumed by wave-3 bootstrap CLI)
if [ -n "$ADMIN_EMAIL" ] || [ -n "$ADMIN_PASSWORD" ]; then
  if [ -z "$ADMIN_EMAIL" ] || [ -z "$ADMIN_PASSWORD" ]; then
    err "Both --admin-email and --admin-password must be supplied together."
    exit 1
  fi
  mkdir -p .helix
  umask 077
  cat > .helix/first-admin.json <<EOF
{
  "email": "${ADMIN_EMAIL}",
  "password": "${ADMIN_PASSWORD}",
  "created_by": "setup.sh",
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
  chmod 600 .helix/first-admin.json
  ok "First-admin credentials staged at .helix/first-admin.json (wave-3 'helix admin bootstrap' will consume)."
fi

# ── 3. Build images ──────────────────────────────────────────────────
log "Building container images (this can take 5-10 min on first run)…"
build_args=()
if $REBUILD; then
  build_args+=(--no-cache --pull)
fi
docker compose "${COMPOSE_FILES[@]}" "${COMPOSE_PROFILES[@]}" build "${build_args[@]}"
ok "Images built."

# ── 4. Start stack ───────────────────────────────────────────────────
log "Starting Postgres + Redis + Temporal…"
docker compose "${COMPOSE_FILES[@]}" "${COMPOSE_PROFILES[@]}" up -d postgres redis temporal

log "Waiting for Postgres to accept connections…"
for i in $(seq 1 30); do
  if docker compose "${COMPOSE_FILES[@]}" "${COMPOSE_PROFILES[@]}" exec -T postgres pg_isready -U "${POSTGRES_USER:-helix}" >/dev/null 2>&1; then
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
docker compose "${COMPOSE_FILES[@]}" "${COMPOSE_PROFILES[@]}" up -d backend worker frontend

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
  err "Backend did not pass /readyz within 120s. Recent logs:"
  docker compose "${COMPOSE_FILES[@]}" "${COMPOSE_PROFILES[@]}" logs --tail=80 backend >&2 || true
  exit 1
fi
ok "Backend ready."

# ── 6. Friendly summary ──────────────────────────────────────────────
frontend_port="${FRONTEND_HOST_PORT:-3000}"
backend_port="${BACKEND_HOST_PORT:-8000}"

# Pick the URL we tell the operator to visit.
if [ -n "$DOMAIN" ]; then
  PUBLIC_FRONTEND="https://${DOMAIN}"
  PUBLIC_BACKEND="https://${DOMAIN}"
else
  PUBLIC_FRONTEND="http://${PUBLIC_HOST}:${frontend_port}"
  PUBLIC_BACKEND="http://${PUBLIC_HOST}:${backend_port}"
fi

cat <<EOF

${C_BOLD}${C_GREEN}Helix is up.${C_RST}

  ${C_BOLD}Frontend${C_RST}   ${PUBLIC_FRONTEND}
  ${C_BOLD}Backend${C_RST}    ${PUBLIC_BACKEND}
  ${C_BOLD}OpenAPI${C_RST}    ${PUBLIC_BACKEND}/docs
  ${C_BOLD}Health${C_RST}     ${PUBLIC_BACKEND}/api/v1/health
  ${C_BOLD}Ready${C_RST}      ${PUBLIC_BACKEND}/api/v1/readyz
  ${C_BOLD}Metrics${C_RST}    ${PUBLIC_BACKEND}/metrics

${C_DIM}# First-time setup — open the frontend and walk through the wizard:${C_RST}
${C_DIM}#   ${PUBLIC_FRONTEND}/setup/first-admin${C_RST}

${C_DIM}# Repo: ${REPO_URL}${C_RST}
${C_DIM}# Common ops:${C_RST}
${C_DIM}#   docker compose ${COMPOSE_FILES[*]} logs -f backend worker${C_RST}
${C_DIM}#   docker compose ${COMPOSE_FILES[*]} ps${C_RST}
${C_DIM}#   ./setup.sh --down            # stop, keep data${C_RST}
${C_DIM}#   ./setup.sh --rotate-secrets --force --confirm-data-loss${C_RST}
${C_DIM}#   docker compose --profile debug up -d temporal-ui  # opt-in Temporal UI on 127.0.0.1:8233${C_RST}

EOF
