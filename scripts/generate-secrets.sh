#!/usr/bin/env bash
# Generate strong random secrets for a Helix deployment.
#
# Writes (or appends to) .env in the repo root. Existing values are kept —
# only blank/default placeholders are filled. Re-running is safe.
#
# Usage:
#   ./scripts/generate-secrets.sh           # writes to .env (creates from .env.example if missing)
#   ./scripts/generate-secrets.sh --force   # overwrites existing values
#   ./scripts/generate-secrets.sh --print   # prints to stdout, doesn't touch .env

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
ENV_LOCAL_FILE="$ROOT_DIR/.env.local"
ENV_EXAMPLE="$ROOT_DIR/.env.example"

FORCE=false
PRINT_ONLY=false
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=true ;;
    --print) PRINT_ONLY=true ;;
    -h|--help)
      sed -n '2,/^$/p' "$0" | sed 's/^# //;s/^#//'
      exit 0
      ;;
  esac
done

# ── Safety: never silently overwrite an .env that still contains placeholder
#   markers (SC-003). If the operator has been editing .env manually we route
#   generated secrets into .env.local instead so nothing is clobbered.
if [ -f "$ENV_FILE" ] && [ "$FORCE" != true ] && [ "$PRINT_ONLY" != true ]; then
  if grep -Eq '=change_me|=helix_password' "$ENV_FILE"; then
    echo "" >&2
    echo "WARNING: $ENV_FILE still contains placeholder markers (change_me / helix_password)." >&2
    echo "         Refusing to overwrite it in place. Writing generated secrets to" >&2
    echo "         $ENV_LOCAL_FILE instead — merge by hand or re-run with --force." >&2
    echo "" >&2
    ENV_FILE="$ENV_LOCAL_FILE"
    if [ ! -f "$ENV_FILE" ]; then
      : > "$ENV_FILE"
    fi
  fi
fi

# ── Generators ───────────────────────────────────────────────────────

rand_hex() {
  # $1 = byte length (output = $1 * 2 hex chars)
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex "$1"
  else
    # Pure-shell fallback. Less entropy on systems without /dev/urandom.
    head -c "$1" /dev/urandom | od -An -tx1 | tr -d ' \n'
  fi
}

rand_base64_urlsafe() {
  # $1 = byte length (output = base64-url string, padding stripped)
  # NOTE: Do NOT use this for ENCRYPTION_KEY — Fernet requires the '=' padding.
  # Use rand_fernet_key() instead.
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -base64 "$1" | tr '/+' '_-' | tr -d '=\n'
  else
    head -c "$1" /dev/urandom | base64 | tr '/+' '_-' | tr -d '=\n'
  fi
}

rand_fernet_key() {
  # Produce a valid 44-char Fernet key (32 bytes, url-safe base64 WITH '=' padding).
  # Fernet requires exactly 44 chars — the trailing '=' MUST be kept.
  # Priority: python3+cryptography > openssl > hard-fail.
  if command -v python3 >/dev/null 2>&1; then
    local _out
    if _out="$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null)"; then
      printf '%s' "$_out"
      return 0
    fi
    # python3 present but cryptography not installed — hard-fail with instructions.
    echo "ERROR: ENCRYPTION_KEY generation needs openssl OR python3-cryptography." >&2
    echo "Install: \`apt install -y python3-cryptography\` OR \`pip install cryptography\`." >&2
    exit 1
  fi
  if command -v openssl >/dev/null 2>&1; then
    # openssl rand 32 emits 32 raw bytes; pipe through base64 then convert +/ to -_
    # but DO NOT strip '=' — Fernet requires the trailing padding char.
    printf '%s' "$(openssl rand 32 | base64 | tr '/+' '_-' | tr -d '\n')"
    return 0
  fi
  # Neither python3 nor openssl available — hard-fail.
  echo "ERROR: ENCRYPTION_KEY generation needs openssl OR python3-cryptography." >&2
  echo "Install: \`apt install -y python3-cryptography\` OR \`pip install cryptography\`." >&2
  exit 1
}

# ── Compose secret values ────────────────────────────────────────────

POSTGRES_PASSWORD_VAL="$(rand_hex 16)"        # 32 hex chars
APP_SECRET_KEY_VAL="$(rand_hex 32)"           # 64 hex chars
JWT_SECRET_KEY_VAL="$(rand_hex 32)"           # 64 hex chars
ENCRYPTION_KEY_VAL="$(rand_fernet_key)"       # 44-char Fernet
AUDIT_HMAC_KEY_VAL="$(rand_hex 32)"           # 64 hex chars (must differ from JWT)
TEMPORAL_UI_PASSWORD_VAL="$(rand_hex 12)"     # 24 hex chars

if [ "$PRINT_ONLY" = true ]; then
  cat <<EOF
POSTGRES_PASSWORD=$POSTGRES_PASSWORD_VAL
APP_SECRET_KEY=$APP_SECRET_KEY_VAL
JWT_SECRET_KEY=$JWT_SECRET_KEY_VAL
ENCRYPTION_KEY=$ENCRYPTION_KEY_VAL
AUDIT_HMAC_KEY=$AUDIT_HMAC_KEY_VAL
TEMPORAL_UI_PASSWORD=$TEMPORAL_UI_PASSWORD_VAL
EOF
  exit 0
fi

# ── Seed .env from .env.example if needed ────────────────────────────

if [ ! -f "$ENV_FILE" ]; then
  if [ -f "$ENV_EXAMPLE" ]; then
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    echo "Created .env from .env.example"
  else
    : > "$ENV_FILE"
    echo "Created empty .env"
  fi
fi

# ── Upsert a KEY=VALUE pair in .env ──────────────────────────────────

upsert() {
  local key="$1"
  local value="$2"
  local current
  current="$(grep -E "^${key}=" "$ENV_FILE" || true)"
  local placeholder_re='^'"$key"'=$|=change_me|=change_me_32_byte_key|=$'

  if [ -z "$current" ]; then
    printf '\n%s=%s\n' "$key" "$value" >> "$ENV_FILE"
    echo "  + set $key"
  elif [ "$FORCE" = true ] || echo "$current" | grep -Eq "$placeholder_re"; then
    # Use a temp file to keep this portable across BSD/GNU sed.
    awk -v k="$key" -v v="$value" 'BEGIN{FS=OFS="="} $1==k{$0=k"="v} {print}' "$ENV_FILE" > "$ENV_FILE.tmp"
    mv "$ENV_FILE.tmp" "$ENV_FILE"
    echo "  ~ updated $key"
  else
    echo "  = kept existing $key (re-run with --force to overwrite)"
  fi
}

echo "Writing secrets to $ENV_FILE"
upsert POSTGRES_USER         "helix"
upsert POSTGRES_PASSWORD     "$POSTGRES_PASSWORD_VAL"
upsert POSTGRES_DB           "helix_metadata"
upsert APP_SECRET_KEY        "$APP_SECRET_KEY_VAL"
upsert JWT_SECRET_KEY        "$JWT_SECRET_KEY_VAL"
upsert ENCRYPTION_KEY        "$ENCRYPTION_KEY_VAL"
upsert AUDIT_HMAC_KEY        "$AUDIT_HMAC_KEY_VAL"
upsert TEMPORAL_UI_PASSWORD  "$TEMPORAL_UI_PASSWORD_VAL"

# DATABASE_URL needs to reflect the generated password.
DB_URL="postgresql://helix:${POSTGRES_PASSWORD_VAL}@postgres:5432/helix_metadata"
upsert DATABASE_URL "$DB_URL"

chmod 600 "$ENV_FILE" 2>/dev/null || true
echo "Done. .env is now populated with generated secrets."
echo "Save this Temporal UI password if you want to access the UI later:"
echo "  TEMPORAL_UI_PASSWORD=$TEMPORAL_UI_PASSWORD_VAL"
