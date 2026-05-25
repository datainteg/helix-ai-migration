#!/usr/bin/env bash
# Helix Migration — Postgres + artifact volume backup.
#
# Run on the same host as the running compose stack. Produces two artifacts:
#   backups/<stamp>/postgres.sql.gz      pg_dump of the metadata database
#   backups/<stamp>/artifacts.tar.gz     contents of the helix_artifacts volume
#
# Optional: upload both to an S3-compatible bucket when HELIX_BACKUP_S3_BUCKET
# is set. Uses the AWS CLI; falls back to local-only when AWS CLI is missing.
#
# Cron (3 a.m. local, retain 30 days locally):
#   0 3 * * * /opt/helix/scripts/backup.sh >> /var/log/helix-backup.log 2>&1
#   30 3 * * * find /opt/helix/backups -mtime +30 -type d -empty -delete

set -euo pipefail

if [ -t 1 ]; then
  C_BLUE=$'\033[34m'; C_GREEN=$'\033[32m'; C_RED=$'\033[31m'; C_RST=$'\033[0m'
else
  C_BLUE=""; C_GREEN=""; C_RED=""; C_RST=""
fi

log()  { printf "%s→%s %s\n" "$C_BLUE" "$C_RST" "$*"; }
ok()   { printf "%s✓%s %s\n" "$C_GREEN" "$C_RST" "$*"; }
err()  { printf "%s✗%s %s\n" "$C_RED" "$C_RST" "$*" >&2; }

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [ -f .env ]; then
  # shellcheck disable=SC1091
  set -a
  . .env
  set +a
fi

POSTGRES_USER="${POSTGRES_USER:-helix}"
POSTGRES_DB="${POSTGRES_DB:-helix_metadata}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
BACKUP_DIR="$ROOT_DIR/backups/$STAMP"
mkdir -p "$BACKUP_DIR"

# ── Postgres dump ────────────────────────────────────────────────────
log "Dumping Postgres → $BACKUP_DIR/postgres.sql.gz"
docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists \
  | gzip > "$BACKUP_DIR/postgres.sql.gz"
ok "Postgres dump: $(du -h "$BACKUP_DIR/postgres.sql.gz" | cut -f1)"

# ── Artifact tarball ─────────────────────────────────────────────────
log "Snapshotting artifact volume → $BACKUP_DIR/artifacts.tar.gz"
VOL_NAME="${COMPOSE_PROJECT_NAME:-helix-ai-migration}_helix_artifacts"
docker run --rm \
  -v "$VOL_NAME:/data:ro" \
  -v "$BACKUP_DIR:/backup" \
  alpine:3 \
  sh -c "cd /data && tar czf /backup/artifacts.tar.gz . && chmod 644 /backup/artifacts.tar.gz"
ok "Artifacts tar: $(du -h "$BACKUP_DIR/artifacts.tar.gz" | cut -f1)"

# ── Manifest ─────────────────────────────────────────────────────────
cat > "$BACKUP_DIR/MANIFEST.txt" <<EOF
Helix Migration backup
Stamp: $STAMP
Host: $(hostname)
Compose project: ${COMPOSE_PROJECT_NAME:-helix-ai-migration}
Postgres user/db: $POSTGRES_USER / $POSTGRES_DB
postgres.sql.gz sha256: $(sha256sum "$BACKUP_DIR/postgres.sql.gz" | awk '{print $1}')
artifacts.tar.gz sha256: $(sha256sum "$BACKUP_DIR/artifacts.tar.gz" | awk '{print $1}')
EOF
ok "Manifest written"

# ── Optional S3 upload ───────────────────────────────────────────────
if [ -n "${HELIX_BACKUP_S3_BUCKET:-}" ]; then
  if ! command -v aws >/dev/null 2>&1; then
    err "HELIX_BACKUP_S3_BUCKET set but aws CLI missing. Skipping upload."
  else
    DEST="s3://${HELIX_BACKUP_S3_BUCKET}/${HELIX_BACKUP_S3_PREFIX:-helix-backups}/$STAMP/"
    log "Uploading → $DEST"
    aws s3 cp "$BACKUP_DIR/" "$DEST" --recursive --only-show-errors
    ok "Upload complete"
  fi
fi

ok "Backup complete: $BACKUP_DIR"
