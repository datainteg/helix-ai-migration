#!/usr/bin/env bash
# Regenerate requirements.lock files for backend + worker.
#
# Runs pip-compile inside a python:3.11-slim Docker container so the resolved
# versions match the production runtime (regardless of which Python the
# developer has installed locally).
#
# Usage:
#   ./scripts/lock-requirements.sh                 # regenerate both
#   ./scripts/lock-requirements.sh backend         # only backend
#   ./scripts/lock-requirements.sh worker          # only worker
#   ./scripts/lock-requirements.sh --upgrade       # bump pinned versions to latest

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

UPGRADE_FLAG=""
TARGETS=("backend" "worker")
for arg in "$@"; do
  case "$arg" in
    --upgrade) UPGRADE_FLAG="--upgrade" ;;
    backend|worker) TARGETS=("$arg") ;;
    -h|--help)
      sed -n '2,/^$/p' "$0" | sed 's/^# //;s/^#//'
      exit 0
      ;;
  esac
done

if ! command -v docker >/dev/null 2>&1; then
  echo "error: docker is required to regenerate the lockfiles." >&2
  exit 1
fi

lock_one() {
  local target="$1"
  echo ">>> Locking $target/requirements.txt → $target/requirements.lock"
  docker run --rm \
    -v "$ROOT_DIR:/work" \
    -w /work \
    python:3.11-slim \
    bash -c "pip install --quiet pip-tools && \
      pip-compile $UPGRADE_FLAG --strip-extras --resolver=backtracking \
        --output-file=$target/requirements.lock \
        $target/requirements.txt"
}

for t in "${TARGETS[@]}"; do
  lock_one "$t"
done

echo ""
echo "Done. Commit the updated $target/requirements.lock file(s)."
