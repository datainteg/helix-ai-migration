#!/usr/bin/env bash
# Helix Migration — restore from a backup directory produced by scripts/backup.sh.
#
# Usage:
#   ./scripts/restore.sh backups/20260525-031500
#   ./scripts/restore.sh s3://my-bucket/helix-backups/20260525-031500   (needs aws CLI)
#
# DESTRUCTIVE — wipes the current Postgres DB + artifact volume contents
# before restoring. Stops the backend + worker first so no writers race
# against the restore. Requires explicit confirmation.

set -euo pipefail

if [ -t 1 ]; then
  C_BLUE=$'\033[34m'; C_GREEN=$'\033[32m'; C_RED=$'\033[31m'; C_YELLOW=$'\033[33m'; C_RST=$'\033[0m'
else
  C_BLUE=""; C_GREEN=""; C_RED=""; C_YELLOW=""; C_RST=""
fi

log()  { printf "%s→%s %s\n" "$C_BLUE" "$C_RST" "$*"; }
ok()   { printf "%s✓%s %s\n" "$C_GREEN" "$C_RST" "$*"; }
warn() { printf "%s!%s %s\n" "$C_YELLOW" "$C_RST" "$*"; }
err()  { printf "%s✗%s %s\n" "$C_RED" "$C_RST" "$*" >&2; }

if [ $# -lt 1 ]; then
  err "Usage: $0 <backup-dir>  (local path or s3://bucket/prefix)"
  exit 1
fi
SRC="$1"

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [ -f .env ]; then
  set -a; . .env; set +a
fi
POSTGRES_USER="${POSTGRES_USER:-helix}"
POSTGRES_DB="${POSTGRES_DB:-helix_metadata}"

# ── Stage the backup locally ─────────────────────────────────────────
STAGE_DIR="$(mktemp -d)"
trap 'rm -rf "$STAGE_DIR"' EXIT

if [[ "$SRC" == s3://* ]]; then
  if ! command -v aws >/dev/null 2>&1; then
    err "aws CLI required for s3:// sources"
    exit 1
  fi
  log "Fetching $SRC → $STAGE_DIR"
  aws s3 cp "$SRC/" "$STAGE_DIR/" --recursive --only-show-errors
else
  log "Copying $SRC → $STAGE_DIR"
  cp -r "$SRC"/* "$STAGE_DIR/"
fi

if [ ! -f "$STAGE_DIR/postgres.sql.gz" ] || [ ! -f "$STAGE_DIR/artifacts.tar.gz" ]; then
  err "Missing postgres.sql.gz or artifacts.tar.gz in backup. Manifest:"
  cat "$STAGE_DIR/MANIFEST.txt" 2>/dev/null || true
  exit 1
fi

# ── Confirm ──────────────────────────────────────────────────────────
warn "This will WIPE the current Postgres database '$POSTGRES_DB' AND the"
warn "helix_artifacts volume. The backend + worker containers will be"
warn "stopped during restore."
read -r -p "Type 'restore' to proceed: " confirm
if [ "$confirm" != "restore" ]; then
  err "Aborted."
  exit 1
fi

# ── Stop writers ─────────────────────────────────────────────────────
log "Stopping backend + worker…"
docker compose stop backend worker || true

# ── Postgres restore ─────────────────────────────────────────────────
log "Restoring Postgres from postgres.sql.gz"
gunzip -c "$STAGE_DIR/postgres.sql.gz" \
  | docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
ok "Postgres restored"

# ── Artifact volume restore ──────────────────────────────────────────
VOL_NAME="${COMPOSE_PROJECT_NAME:-helix-ai-migration}_helix_artifacts"
log "Wiping artifact volume + extracting artifacts.tar.gz"
docker run --rm \
  -v "$VOL_NAME:/data" \
  -v "$STAGE_DIR:/backup:ro" \
  alpine:3 \
  sh -c "find /data -mindepth 1 -delete && tar xzf /backup/artifacts.tar.gz -C /data"
ok "Artifacts restored"

# ── Restart workers ──────────────────────────────────────────────────
log "Restarting backend + worker…"
docker compose start backend worker
ok "Restore complete. Verify /api/v1/audit-logs/verify integrity check passes."
