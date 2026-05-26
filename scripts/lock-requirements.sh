#!/usr/bin/env bash
# Regenerate requirements.lock files for backend + worker.
#
# Runs pip-compile inside a python:3.11-slim-bookworm Docker container so the
# resolved versions match the production runtime (Python 3.11, Linux).
#
# The lock files MUST be generated with Python 3.11 on Linux to match the
# production container runtime. Any mismatch will cause ABI-incompatible wheels
# to be selected (e.g., cp313 wheels on a 3.11 interpreter, or Windows wheels
# on Linux), breaking at container startup.
#
# Usage:
#   ./scripts/lock-requirements.sh                 # regenerate both (via Docker)
#   ./scripts/lock-requirements.sh backend         # only backend (via Docker)
#   ./scripts/lock-requirements.sh worker          # only worker (via Docker)
#   ./scripts/lock-requirements.sh --upgrade       # bump pinned versions to latest
#
# ENFORCEMENT:
# - Will refuse to run outside Docker unless --via-docker is passed.
# - On non-Linux systems (macOS, Windows), Docker provides the Linux environment.
# - On Linux, will assert python3 version is 3.11.x unless --via-docker is passed.
# - Use --via-docker to skip the environment check (Docker always provides the
#   correct environment).

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

UPGRADE_FLAG=""
VIA_DOCKER=false
TARGETS=("backend" "worker")

for arg in "$@"; do
  case "$arg" in
    --upgrade) UPGRADE_FLAG="--upgrade" ;;
    --via-docker) VIA_DOCKER=true ;;
    backend|worker) TARGETS=("$arg") ;;
    -h|--help)
      sed -n '2,/^$/p' "$0" | sed 's/^# //;s/^#//'
      exit 0
      ;;
    *)
      echo "error: unknown argument '$arg'" >&2
      exit 1
      ;;
  esac
done

# Enforce environment: require Docker (always available) or match Python 3.11 on Linux.
if ! command -v docker >/dev/null 2>&1; then
  echo "error: docker is required to regenerate the lockfiles." >&2
  exit 1
fi

if [ "$VIA_DOCKER" = false ]; then
  # Check if we are on Linux with Python 3.11; otherwise require --via-docker.
  if [ "$(uname -s)" != "Linux" ]; then
    # Not on Linux (macOS, Windows, etc). Docker will provide the correct env.
    # Silently use Docker (this is the normal case for local dev).
    VIA_DOCKER=true
  else
    # We are on Linux. Check Python version.
    python_version=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' || echo "")
    if [ -z "$python_version" ] || ! echo "$python_version" | grep -qE '^3\.11'; then
      echo "error: Python 3.11.x is required to regenerate lockfiles on Linux." >&2
      echo "       Your Python version: $(python3 --version 2>&1)" >&2
      echo "       Use 'docker run' or pass --via-docker to use Docker." >&2
      exit 1
    fi
  fi
fi

# Once validated, always use Docker (--via-docker just skips the check).
VIA_DOCKER=true

lock_one() {
  local target="$1"
  echo ">>> Locking $target/requirements.txt → $target/requirements.lock"
  echo "    (using python:3.11-slim-bookworm in Docker for reproducibility)"
  docker run --rm \
    -v "$ROOT_DIR:/work" \
    -w /work \
    python:3.11-slim-bookworm \
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
