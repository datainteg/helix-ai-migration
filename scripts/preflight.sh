#!/usr/bin/env bash
# scripts/preflight.sh — hardware + port sanity check.
# Invoked by setup.sh. Exits 0 on pass, 1 on fatal, 2 on warn-only.
# Cross-ref: docs/review-v4/DEPLOY_SETUP.md DSETUP-027, DSETUP-032.
set -eu

warn() { printf "! %s\n" "$*" >&2; }
err()  { printf "x %s\n" "$*" >&2; }

# RAM (need >= 2 GB to boot, recommend 4 GB).
if [ -r /proc/meminfo ]; then
  mem_kb=$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)
  mem_gb=$(( mem_kb / 1024 / 1024 ))
  if [ "$mem_gb" -lt 2 ]; then
    err "Only ${mem_gb} GB RAM. Need >= 4 GB for production (2 GB to boot)."
    exit 1
  elif [ "$mem_gb" -lt 4 ]; then
    warn "Only ${mem_gb} GB RAM. Stack will boot but may OOM under load."
  fi
fi

# Disk (need >= 10 GB free where the repo lives).
disk_gb=$(df -BG --output=avail . 2>/dev/null | tail -1 | tr -dc '0-9')
if [ -n "${disk_gb:-}" ] && [ "$disk_gb" -lt 10 ]; then
  err "Only ${disk_gb} GB free on $(pwd). Need >= 10 GB (20 GB recommended)."
  exit 1
fi

# Port conflicts on the host (compose binds these by default).
check_port() {
  local p="$1"
  if command -v ss >/dev/null 2>&1; then
    if ss -ltn 2>/dev/null | awk '{print $4}' | grep -qE "[:.]${p}\$"; then
      warn "Port ${p} already bound on host. Change BACKEND_HOST_PORT / FRONTEND_HOST_PORT in .env (or BACKEND_BIND / FRONTEND_BIND to change the interface)."
    fi
  elif command -v lsof >/dev/null 2>&1; then
    if lsof -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1; then
      warn "Port ${p} already bound on host."
    fi
  fi
}
for p in "${BACKEND_HOST_PORT:-8000}" "${FRONTEND_HOST_PORT:-3000}"; do
  check_port "$p"
done

exit 0
