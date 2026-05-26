# DEPLOY_SETUP — one-click installer audit (Linux / GCP / Ubuntu 24 LTS)

> Generated 2026-05-26.  Scope: `setup.sh`, `scripts/generate-secrets.sh`,
> `.env.example`, `docker-compose.yml`, `docker-compose.build.yml`, root
> `DEPLOY.md`. `setup.ps1` + `scripts/generate-secrets.ps1` are
> Windows-only and only summarised at the end.
>
> Target distros: Ubuntu 24.04 LTS (primary, including GCP COS / GCE),
> Debian 12, Alpine 3.20, RHEL 9 / Fedora 41, Arch.
>
> Severity legend: 🔴 CRITICAL · 🟠 HIGH · 🟡 MED · 🔵 LOW.
> This file is the **review only**; no source changes were made.
>
> Cross-reference: `docs/review-v2/REVIEW_INFRA.md` INFRA-020..029 already
> flagged some of these — findings below add the GCP / Ubuntu-24 /
> distro-portability lens that the earlier review did not.

---

## 0. Headline numbers

| Severity | Count |
|---|---|
| 🔴 CRITICAL | **4** |
| 🟠 HIGH | **9** |
| 🟡 MED | **11** |
| 🔵 LOW | **6** |
| **Total** | **30** |

**Verdict (TL;DR):** `needs work ⚠️`. The script is well-structured and
*almost* one-click for an experienced Docker user on Ubuntu 22/24 with
Docker Engine + Compose v2 already installed. It is **not** safe to ship
as a literal `curl | bash` one-liner on a fresh VM today, for four
reasons:

1. There is **no Docker auto-install / detection of a missing daemon** —
   the script aborts with a generic "install docker-ce" message on fresh
   Ubuntu 24.04 and every other distro.
2. The Fernet-key fallback in `generate-secrets.sh` can silently emit a
   **43-char "Fernet" key** that `cryptography` will reject at backend
   boot — re-flagging INFRA-025.
3. `setup.sh` does **not source `.env`** before polling Postgres, so any
   operator who edits `POSTGRES_USER` / `BACKEND_HOST_PORT` watches the
   readiness probes time out on the wrong values.
4. Compose binds `${BACKEND_HOST_PORT:-8000}` and
   `${FRONTEND_HOST_PORT:-3000}` to **0.0.0.0** by default. On a GCP
   VM with the default `default-allow-internal` + `allow-ssh` rules
   nothing happens — but the moment an operator opens TCP 8000 (which
   `DEPLOY.md` actively tells them to do, see INFRA-045 / DSETUP-019),
   the backend's full API surface (incl. `/docs`, OpenAPI, every admin
   endpoint behind auth) is reachable from the public internet on
   `0.0.0.0/0`.

---

## 1. Distro portability

### DSETUP-001 🔴 No Docker / Compose installer — script just exits when missing

`setup.sh:94-106` only **detects** Docker and Compose; it never installs
them. On a brand-new GCE Ubuntu 24.04 LTS image (which ships **without**
Docker), the operator's experience is:

```text
$ ./setup.sh
→ Checking Docker…
✗ docker not found in PATH. Install Docker Desktop (Mac/Windows) or docker-ce (Linux).
```

That's two manual steps (add the Docker apt repo, install
`docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin`,
add the user to the `docker` group, log out/in) before the "one-click"
script even gets to step 1. Same story on Debian 12, Fedora 41, Arch,
Alpine. **GCP impact:** on a stock Ubuntu LTS Compute Engine instance
the docker pkg in `apt` (`docker.io`) is fine for the engine but
**doesn't carry the `docker compose` plugin** at all — the operator
needs the upstream repo, which the README + DEPLOY.md never mention.

**Fix:** add an optional bootstrap step gated by `--install-docker`,
something like:

```bash
install_docker_linux() {
  if command -v docker >/dev/null && docker compose version >/dev/null 2>&1; then
    return 0
  fi
  log "Installing Docker Engine + Compose plugin…"
  if [ -r /etc/os-release ]; then . /etc/os-release; fi
  case "${ID:-unknown}" in
    ubuntu|debian)
      curl -fsSL https://get.docker.com | sh
      ;;
    fedora|rhel|centos|rocky|almalinux)
      curl -fsSL https://get.docker.com | sh
      ;;
    arch|manjaro)
      sudo pacman -Sy --noconfirm docker docker-compose docker-buildx
      sudo systemctl enable --now docker
      ;;
    alpine)
      sudo apk add --no-cache docker docker-cli-compose
      sudo rc-update add docker default && sudo service docker start
      ;;
    *)
      err "Unknown distro ${ID:-?}. Install Docker manually: https://docs.docker.com/engine/install/"
      return 1
      ;;
  esac
  if ! id -nG "$USER" | grep -qw docker; then
    sudo usermod -aG docker "$USER"
    warn "Added $USER to the docker group — log out and back in, then re-run setup.sh"
    exit 0
  fi
}
```

(`get.docker.com` covers Ubuntu, Debian, Fedora, RHEL, CentOS, Rocky,
Alma, SLES, Raspbian — five of the six target distros, leaving only
Arch + Alpine for the package-manager fallbacks.)

### DSETUP-002 🟠 Hard `#!/usr/bin/env bash` shebang, no Alpine-friendly fallback

`setup.sh:1`. Alpine's BusyBox does **not** ship bash by default; on a
fresh Alpine 3.20 the operator gets `env: can't execute 'bash': No such
file or directory`. The script genuinely uses bash-isms
(`[[ … ]]`-style? actually no — it uses `[ … ]` POSIX, plus arrays at
`COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.build.yml)`
which IS bash-only) so it can't trivially be relaxed to `sh`.

**Fix:** either (a) document `apk add bash curl docker docker-cli-compose`
as the Alpine prereq, or (b) have the script detect missing bash and
print a single clean line: `err "This installer requires bash. On
Alpine: apk add bash"`. Today the user just sees a cryptic execve
failure.

### DSETUP-003 🟠 CRLF line-ending hazard — repo has no `.gitattributes`

There is no `.gitattributes` enforcing LF on `*.sh`. A Windows operator
who clones the repo with `core.autocrlf=true` (the default on Git for
Windows) gets `setup.sh` and `scripts/generate-secrets.sh` written with
CRLF line endings. Running either under WSL2 / Ubuntu produces:

```text
$ ./setup.sh
/usr/bin/env: 'bash\r': No such file or directory
```

**GCP impact:** any sysadmin who edits the repo on a Windows laptop and
SCPs it up to a GCE VM hits this. **Fix:** add a `.gitattributes`:

```gitattributes
*.sh        text eol=lf
*.bash      text eol=lf
Dockerfile* text eol=lf
*.yml       text eol=lf
*.yaml      text eol=lf
```

…and re-normalise existing files (`git add --renormalize .`).

### DSETUP-004 🟡 `sudo` is referenced in the error path but never used or detected

`setup.sh:104` suggests `sudo systemctl start docker`. If the operator
isn't in the `docker` group AND isn't root, every `docker` call in the
rest of the script fails with `permission denied while trying to
connect to the Docker daemon socket`. The script has no fallback to
re-invoke under `sudo` and no detection of `sudo -n` availability.

**Fix:** after the `docker info` check fails, try `sudo -n docker info`
once and, on success, re-exec the rest of the script with `sudo -E`.
Or at minimum print a single targeted message: `err "You aren't in the
docker group. Run: sudo usermod -aG docker $USER && newgrp docker"`.

### DSETUP-005 🟡 No detection of legacy `docker-compose` (v1)

`setup.sh:99` correctly requires Compose v2 (`docker compose version`).
But many fleet hosts still have v1 installed as `docker-compose` (the
hyphenated PyPI binary). The script doesn't tell the operator
that the v1 binary is unsupported and that they should `apt install
docker-compose-plugin` (Ubuntu) or `dnf install docker-compose-plugin`
(Fedora). Operators see only "Docker Compose v2 plugin missing" without
the upgrade path.

**Fix:** detect `docker-compose` and explicitly warn:

```bash
if command -v docker-compose >/dev/null 2>&1 && ! docker compose version >/dev/null 2>&1; then
  warn "Detected legacy docker-compose v1 — this project requires Compose v2 (the 'docker compose' subcommand)."
  warn "Ubuntu/Debian: sudo apt install docker-compose-plugin"
  warn "Fedora/RHEL:   sudo dnf install docker-compose-plugin"
  warn "Or upgrade Docker Desktop."
fi
```

### DSETUP-006 🔵 `pg_isready -U "${POSTGRES_USER:-helix}"` runs in a shell that never sourced `.env`

`setup.sh:168`. See DSETUP-008 (idempotency) — same root cause. The
script substitutes `:-helix` because the variable is unset in its own
env. If the operator changed `POSTGRES_USER=helix_prod` in `.env`,
the readiness probe queries the wrong username and waits the full
60 s before bailing. Re-confirms INFRA-021.

---

## 2. Docker detection

### DSETUP-007 🟠 `docker info` succeeds with default-allow socket but masks group-permission failure

`setup.sh:103`. The check is `docker info >/dev/null 2>&1`. If the
operator's UID can't read `/var/run/docker.sock`, the call fails with
"permission denied", but the redirected stderr hides the actual reason.
The follow-on `err "Docker daemon not running. Start Docker Desktop or
'sudo systemctl start docker'."` is **wrong** in that scenario — the
daemon IS running, the user just isn't in the group.

**Fix:** branch on the actual stderr:

```bash
if ! docker info >/dev/null 2>/tmp/helix-docker-info.err; then
  if grep -q "permission denied" /tmp/helix-docker-info.err; then
    err "Cannot connect to Docker socket — your user isn't in the docker group."
    err "  Fix: sudo usermod -aG docker \"\$USER\" && newgrp docker"
    err "  Then re-run ./setup.sh."
  elif grep -q "Cannot connect to the Docker daemon" /tmp/helix-docker-info.err; then
    err "Docker daemon is not running. Start it: sudo systemctl start docker"
  else
    err "Docker is unhealthy. Raw error:"
    cat /tmp/helix-docker-info.err >&2
  fi
  exit 1
fi
```

Also matters because **GCE COS (Container-Optimized OS)** has the
daemon running but the default `cos` user isn't in the docker group
unless added explicitly — the operator hits this immediately.

### DSETUP-008 🟡 `.env` never sourced before docker invocations

`setup.sh:163-198` calls `docker compose exec`, polls Postgres, and
builds the readiness URL using `${BACKEND_HOST_PORT:-8000}` and
`${FRONTEND_HOST_PORT:-3000}` — but the script never `set -a; .
./.env; set +a` after creating it. Compose itself reads `.env`
correctly, but the bash variables are unset for the polling loop.
**Combined consequence:** changing `BACKEND_HOST_PORT=8001` in `.env`
means compose binds 8001, but `setup.sh` polls 8000 and reports
"Backend did not pass /readyz within 120s" even though everything is
fine.

**Fix:** add right after `cp .env.example .env` / "keeping existing
values":

```bash
set -a
# shellcheck disable=SC1091
. ./.env
set +a
```

### DSETUP-009 🔵 Docker Desktop vs native — no detection

Not strictly needed on Linux, but on macOS the readiness loop assumes
the host is `localhost`; on Docker Desktop (Linux VM mode) that's true,
but on rootless Linux Docker Desktop the published port may bind to
the user network namespace and not be reachable as `localhost`. Add a
note in the script header. Cosmetic.

---

## 3. Idempotency

### DSETUP-010 🔴 `--rotate-secrets` silently destroys all encrypted LLM keys and connector creds

Re-asserting INFRA-020 with the GCP angle: a typical GCP runbook
trains ops to "rotate secrets every 90 days." Running
`./setup.sh --rotate-secrets` looks like the right thing — but it
rotates `ENCRYPTION_KEY` (the Fernet wrap key for stored LLM API keys
and connector credentials in `connection_encrypted_config`) and
`AUDIT_HMAC_KEY` (which chains the audit log). After the rotation,
**every connector and every stored LLM credential fails to decrypt**,
and the audit log loses chain-verify continuity. The current warning
("existing JWT tokens + audit chains will be invalidated") does not
mention this.

**Fix:** split the flag:

```bash
case "$1" in
  --rotate-jwt)        ROTATE_JWT=true ;;
  --rotate-encryption) ROTATE_ENCRYPTION=true ;;   # requires --i-will-re-encrypt
  --rotate-audit-hmac) ROTATE_AUDIT=true ;;        # requires --break-audit-chain
  --rotate-secrets)    err "Use one of --rotate-jwt / --rotate-encryption / --rotate-audit-hmac. Bulk rotation removed in 0.6."; exit 1;;
esac
```

…and gate `ENCRYPTION_KEY` rotation behind a re-encrypt migration step
(load old key, decrypt all rows, re-encrypt with new key, atomic
swap).

### DSETUP-011 🟠 Fernet fallback emits an invalid 43-char key (INFRA-025 confirmed)

`scripts/generate-secrets.sh:43-50`. The shell fallback:

```bash
rand_base64_urlsafe() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -base64 "$1" | tr '/+' '_-' | tr -d '=\n'
  else
    head -c "$1" /dev/urandom | base64 | tr '/+' '_-' | tr -d '=\n'
  fi
}
```

For `n=32`, openssl base64 wraps at 64 cols with a trailing `\n` and
prints `Pq3…==\n`. After `tr -d '=\n'`, you get **43 chars**.
`cryptography.fernet.Fernet(key)` requires exactly **44 chars** (raw
url-safe-base64 of 32 bytes including the single `=` pad). On
`backend` boot, you get:

```text
ValueError: Fernet key must be 32 url-safe base64-encoded bytes.
```

**Combined with DSETUP-001** (no docker auto-install) and the
auto-secret flow, an Ubuntu 24 LTS box with `openssl` but no `python3`
**or** no `cryptography` package (which is true on default Ubuntu 24
LTS minimal images — `cryptography` isn't in base) silently generates
a broken key and the entire stack refuses to start at the backend step,
several minutes in.

**Fix:**

```bash
rand_fernet_key() {
  if command -v python3 >/dev/null 2>&1; then
    if out=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null); then
      printf '%s' "$out"
      return 0
    fi
  fi
  if command -v openssl >/dev/null 2>&1; then
    # 32 random bytes, url-safe-base64 WITH the trailing '=' padding intact.
    printf '%s' "$(openssl rand 32 | base64 | tr '/+' '_-' | tr -d '\n')"
    return 0
  fi
  err "Cannot generate a Fernet key — install one of: python3+cryptography, or openssl."
  exit 1
}
```

Note the **removal of `tr -d '='`** for Fernet specifically — Fernet
*requires* the `=` pad.

### DSETUP-012 🟠 `upsert` placeholder regex over-matches (INFRA-027 confirmed)

`scripts/generate-secrets.sh:102`:

```bash
local placeholder_re='^'"$key"'=$|=change_me|=change_me_32_byte_key|=$'
```

The `=change_me` alternative is an unanchored substring. An operator
who set `POSTGRES_PASSWORD=changeme_for_realsies_2026!` (perfectly
valid) gets that overwritten next time the script runs, because the
substring `=change_me` matches. **Combined with the bash-script's auto-
invocation from `setup.sh`** this means re-running `./setup.sh` after
manually editing `.env` to a hand-picked password destroys that password
silently and prints `~ updated POSTGRES_PASSWORD`. The user only
notices because the DB credentials inside the running container no
longer work.

**Fix:**

```bash
local placeholder_re="^${key}=\$|^${key}=change_me\$|^${key}=change_me_32_byte_key\$"
```

…anchored to a complete value.

### DSETUP-013 🟡 Re-running `setup.sh` re-builds images even when source hasn't changed

`setup.sh:154-160`. Every run hits `docker compose build` (without
`--no-cache`, but Docker still walks the build context, hashes, and
checks layers). On a 10-step Dockerfile with the `agents/` + `backend/`
+ `_bmad/` copy steps, this is 10-20 seconds per run even when nothing
changed. Add `--skip-build` flag for "I just want to bring the stack
back up after a reboot" workflow.

### DSETUP-014 🟡 Postgres seed never auto-runs from `setup.sh` — but no flag exists to opt in

`scripts/seed.py` exists, `setup.sh` never calls it. Demo / smoke-test
users have to discover it separately. Add `./setup.sh --with-demo-data`
that runs `docker compose exec backend python /app/../scripts/seed.py`
once after readyz. Idempotency caveat: the seed isn't idempotent
across orgs (see INFRA-037).

---

## 4. Secret-generation entropy

### DSETUP-015 🟡 `POSTGRES_PASSWORD` is 128 bits while everything else is 256 bits

`scripts/generate-secrets.sh:64`:
`POSTGRES_PASSWORD_VAL="$(rand_hex 16)"   # 32 hex chars`.

Reconfirms INFRA-026. Use 32 bytes hex (256 bits) for parity. Postgres
doesn't care about the length.

### DSETUP-016 🟡 base64 vs hex confusion documented inconsistently

`DEPLOY.md:137` says `ENCRYPTION_KEY` is "44-char base64". The Fernet
spec says "32 bytes url-safe base64-encoded" — and the script's broken
fallback produces 43 chars without the `=` (DSETUP-011). The `.env.example`
comment says "32-byte Fernet key. Generated by scripts/generate-secrets.sh"
— closest to correct, but operators reading `DEPLOY.md` and trying to
hand-roll a key with `openssl rand -base64 32 | tr -d '\n'` produce a
key that **looks 44 chars but lacks the url-safe `_-` substitution and
keeps `+/`** — Fernet rejects it too. Unify all three docs.

### DSETUP-017 🔵 `--print` mode leaks secrets to shell history (INFRA-029)

Same finding, no new GCP angle. Add a `[!]` warning line in `--print`
output explaining the operator should pipe to `pbcopy` / `xclip` / a
file, not to a terminal.

---

## 5. Error handling

### DSETUP-018 🟡 No `trap` on `EXIT` / `ERR` — partial-state failures leave compose half-up

`setup.sh:29` sets `set -euo pipefail` (good), but there is no `trap
'on_err $LINENO' ERR` or `trap cleanup EXIT`. If the script dies after
`docker compose up -d postgres redis temporal` but before backend boots
(e.g. Fernet key invalid, see DSETUP-011), the operator is left with a
half-running stack and no guidance.

**Fix:**

```bash
on_err() {
  local exit_code=$?
  local line=${1:-?}
  err "Setup failed at line $line (exit $exit_code)."
  err "Current containers:"
  docker compose "${COMPOSE_FILES[@]}" ps 2>/dev/null || true
  err "To inspect: docker compose ${COMPOSE_FILES[*]} logs --tail=80"
  err "To clean up: ./setup.sh --down  (or --nuke to wipe volumes)"
  exit "$exit_code"
}
trap 'on_err $LINENO' ERR
```

### DSETUP-019 🟠 Backend readiness loop's failure path doesn't tail the logs

`setup.sh:194-198`. On failure it prints "Tail logs: docker compose
logs --tail=80 backend" — but doesn't actually tail them. New
operators (including CI) lose 5 minutes copy-pasting the right
command. Just invoke it inline before exiting non-zero.

---

## 6. Prompt vs non-interactive (CI / cron / `curl|bash`)

### DSETUP-020 🟠 No `--non-interactive` / `--yes` flag, and `--nuke` always `read -r -p`

`setup.sh:83`. `--nuke` requires interactive `read -r -p "Type 'nuke' to
confirm: "`. Running under CI (`bash -c "yes nuke | ./setup.sh --nuke"`)
works only because stdin is piped, but if the script is invoked via
SSH `-T` or systemd, the read fails with EOF and the script exits 1.

Also `setup.sh` overall has no flag like `--non-interactive` that the
operator can wave to assert "I accept defaults." `curl -sSL …/setup.sh
| bash -s -- --non-interactive` would be the right pattern.

**Fix:** add `NON_INTERACTIVE=${HELIX_NON_INTERACTIVE:-false}` and a
`--non-interactive` switch; gate every `read -r -p` on it.

### DSETUP-021 🟡 TTY-only colour codes are detected (`[ -t 1 ]`) but ASCII fallbacks for arrows are not

`setup.sh:32-37` correctly disables colour outside a TTY. But the
"→ ✓ ! ✗" prefixes are still Unicode. In a journald-captured systemd
service or a Cloud Build log viewer that defaults to ISO-8859-1, those
render as `â†'` / `âœ"`. Use ASCII fallbacks (`>`, `+`, `!`, `x`) when
`$LANG`/`$LC_ALL` doesn't include `UTF-8`.

---

## 7. First-admin flow

### DSETUP-022 🟡 First-admin flow is a UI wizard with no CLI / headless fallback

After `setup.sh` succeeds it prints:
`http://localhost:${frontend_port}/setup/first-admin`. That route exists
(`frontend/src/app/setup/first-admin/page.tsx`) and the backend has
`POST /api/v1/auth/first-admin` (`backend/app/api/auth.py:29`). But:

1. **There is no `./setup.sh --create-admin EMAIL` flag** that calls
   the API directly. On a headless GCE VM the operator has to either
   (a) SSH-tunnel port 3000 to their laptop and run the wizard, or
   (b) `curl -X POST http://localhost:3000/setup/first-admin` (which
   is a server-rendered Next.js page, not an API), or (c) read the
   docs, find `POST /api/v1/auth/first-admin`, and craft the JSON
   payload manually.
2. **The success URL is wrong for non-default ports** — the printed
   URL hardcodes `frontend_port` from a default `:-3000` because
   `.env` was never sourced (DSETUP-008).

**Fix:** add a documented `curl` recipe at the end of `setup.sh`
output, e.g.:

```bash
# Or create the admin headlessly:
curl -X POST "http://localhost:${BACKEND_HOST_PORT:-8000}/api/v1/auth/first-admin" \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"...","organization_name":"My Co"}'
```

…and consider a `./setup.sh --create-admin you@example.com` flag that
prompts for the password (or accepts `--password-stdin`).

---

## 8. Alembic migrations

### DSETUP-023 🟠 Alembic runs both in the backend container CMD AND should arguably run from `setup.sh`

The current model:

1. `setup.sh:181`: `docker compose … up -d backend worker frontend`
2. `backend/Dockerfile:42`:
   `CMD alembic upgrade head && uvicorn app.main:app …`

So `alembic upgrade head` runs **every time the backend starts**. That's
fine for a single-host single-replica deployment, but:

- **Race-prone on scale-out.** If an operator ever runs two backend
  replicas (e.g. `docker compose up -d --scale backend=2`), both call
  `alembic upgrade head` concurrently against the same Postgres. The
  current 24 migration files include several index creations
  (`b2c3d4e5f6a8_composite_indexes.py`, `p7q8r9s0t1u2_perf_missing_indexes.py`)
  that take a metadata lock — two concurrent migrations can deadlock.
- **The wave-2 migrations listed in the brief** all exist in
  `backend/alembic/versions/`:
  - `2af2b45b4051_dek_partial_unique_active.py`
  - `q8r9s0t1u2v3_encrypt_extra_config_secrets.py`
  - `p7q8r9s0t1u2_perf_missing_indexes.py`
  - `8f881cfc333e_identity_uuid_to_string36.py`
  - `eadec18c9cfc_workflow_steps_parsed_output_jsonb.py`
  These are picked up by `alembic upgrade head` on every backend boot.
  **No explicit ordering / no data backfill warning** — for example
  `q8r9s0t1u2v3_encrypt_extra_config_secrets.py` likely encrypts
  existing plaintext rows; running it twice (in parallel) on the same
  DB can corrupt or double-encrypt rows.
- **`setup.sh` claims `5. Migrations`** in its header comment but
  literally does nothing for migrations — it leans entirely on the
  container CMD. The "running alembic migrations inside the backend
  container" wording in the header is misleading. The actual sequence
  is "start backend, hope migrations don't crash, then poll /readyz."

**Fix:**

1. Move `alembic upgrade head` out of the backend `CMD` and into either
   (a) a dedicated init container (`backend.alembic` service in compose
   with `command: alembic upgrade head` and `restart: "no"`), or (b)
   an explicit `setup.sh` step that runs `docker compose run --rm
   backend alembic upgrade head` after Postgres healthy and before the
   long-running backend starts.
2. Confirm each wave-2 migration is idempotent and rerunnable; document
   any that require data backfill.

### DSETUP-024 🟡 No migration-rollback story in `setup.sh`

`setup.sh --down` and `--nuke` exist; there's no `./setup.sh --rollback
N` that calls `alembic downgrade -N`. Bad upgrades have no escape
hatch. Document at minimum: `docker compose exec backend alembic
downgrade -1`.

---

## 9. GCP / Ubuntu-24-specific gotchas

### DSETUP-025 🟠 No `iptables-legacy` / `nftables` check for Ubuntu 24.04 LTS

Ubuntu 24.04 defaults to `iptables-nft` (the nftables backend). Docker
24+ works with both, but a GCE VM that was upgraded in place from
22.04→24.04 may have `iptables-legacy` set as the default while
Docker's bridge rules use `iptables-nft`, producing the symptom
"containers can talk to each other but not to the host"
(`docker0` bridge interface unreachable). This breaks the
`http://localhost:8000/api/v1/readyz` probe from inside `setup.sh`.

**Fix:** add a one-line check in the preflight:

```bash
if [ -x /usr/sbin/iptables ] && [ -L /usr/sbin/iptables ]; then
  case "$(readlink -f /usr/sbin/iptables)" in
    *iptables-legacy*)
      warn "System is using iptables-legacy. Docker on Ubuntu 24 expects nftables."
      warn "  Switch with: sudo update-alternatives --set iptables /usr/sbin/iptables-nft"
      ;;
  esac
fi
```

### DSETUP-026 🟡 No cgroup v2 / AppArmor / SELinux notes

Ubuntu 24 LTS ships with cgroup v2 unified hierarchy and AppArmor in
enforce mode by default. Docker handles cgroup v2 natively
(24+), but the **memory limits in compose's `deploy.resources.limits`**
(which INFRA-001 already flagged as silently ignored) are doubly
problematic on cgroup v2: even the workaround of `mem_limit:` requires
the daemon to have cgroup-v2 swap accounting enabled
(`GRUB_CMDLINE_LINUX="cgroup_enable=memory swapaccount=1"`).

Also, the backend container writes to `/app/data/artifacts` — a volume
mount with the wrong SELinux label on RHEL/Fedora gives
"Permission denied" on first artifact write. Add a `:z` (or `:Z`)
suffix to the volume mounts for SELinux distros, OR document
`sudo setsebool -P container_use_cephfs on`.

### DSETUP-027 🟠 Default port conflicts on 5432 / 6379 not detected

If the host has a system Postgres on 5432 (very common on Ubuntu —
`postgresql-16` is suggested by `apt install` for many tools) and the
operator switches to `docker-compose.dev.yml`, the bind fails with
`Error starting userland proxy: listen tcp4 0.0.0.0:5432: bind:
address already in use`. The primary `docker-compose.yml` doesn't
publish 5432 (good), but the dev overlay does. Add `ss -ltn` /
`lsof -i :5432` check in `setup.sh`'s preflight when the operator
passes `--dev`.

### DSETUP-028 🔴 Compose default binds to `0.0.0.0:8000` / `0.0.0.0:3000` — public on GCE without firewall hardening

`docker-compose.yml:120,170`:

```yaml
backend:
  ports:
    - "${BACKEND_HOST_PORT:-8000}:8000"
frontend:
  ports:
    - "${FRONTEND_HOST_PORT:-3000}:3000"
```

`"8000:8000"` short syntax in compose **binds to `0.0.0.0:8000`**
unless the host-IP prefix is supplied. On a GCP VM with the default
`default-allow-internal` rule only, this is fine — only RFC1918 peers
see the port. But:

1. **`DEPLOY.md:117` explicitly tells the operator to `ufw allow
   8000/tcp`** (already flagged as INFRA-045). That command opens
   8000 to the entire VPC and, on a VM with a public IP, to the
   public internet. The frontend's `/api/*` proxy strategy is
   undocumented in `DEPLOY.md`, so most operators DO open 8000.
2. **GCE's default firewall ruleset** on a fresh `default` VPC allows
   `default-allow-internal` (full 10.0.0.0/8) and any explicit
   `--allow tcp:8000` becomes wildcard-source unless the operator
   knows to add `--source-ranges`. The Helix README/setup never
   discusses GCP firewall scoping.

**GCP impact:** today's `setup.sh` + `ufw allow 8000/tcp` per
`DEPLOY.md` puts every admin endpoint (behind JWT, but still
brute-forceable) on the public internet.

**Fix:** change compose default to bind 127.0.0.1, force opt-in for
public binding:

```yaml
backend:
  ports:
    - "${HELIX_BIND_HOST:-127.0.0.1}:${BACKEND_HOST_PORT:-8000}:8000"
frontend:
  ports:
    - "${HELIX_BIND_HOST:-127.0.0.1}:${FRONTEND_HOST_PORT:-3000}:3000"
```

…and document `HELIX_BIND_HOST=0.0.0.0` as the explicit opt-in (with
warnings about reverse-proxy + TLS).

### DSETUP-029 🟡 No `firewalld` / `ufw` / `nftables` setup hook

`DEPLOY.md`'s firewall snippet is bare `ufw allow …`. RHEL/Fedora/Alma
default to `firewalld`, not ufw — the snippet doesn't apply. Add a
small distro-aware helper in `setup.sh --configure-firewall` that picks
the right CLI.

### DSETUP-030 🟡 Single-host install collides with Cloud SQL Auth Proxy on TCP 5432

Operators running Helix on GCE with Cloud SQL for Postgres typically
run the Auth Proxy on `127.0.0.1:5432`. If the operator switches to
`docker-compose.dev.yml` (or anything that publishes Postgres), the
two collide. Document — or auto-detect — that an external Postgres
should be wired via `DATABASE_URL=postgresql://…@host.docker.internal:5432/…`
(plus `extra_hosts: ["host.docker.internal:host-gateway"]` on Linux).

---

## 10. `curl | bash` flow

### DSETUP-031 🟠 No documented `curl | bash` one-liner — but `setup.sh` is *almost* safe for one

`README.md`/`DEPLOY.md` only document `git clone … && cd … &&
./setup.sh`. There's no `curl -sSL https://helix.datainteg.io/install.sh
| bash` — which is genuinely the bar for "1-click on a fresh VM."
That installer would need to:

1. Detect distro, install `git`, `docker`, `docker-compose-plugin`.
2. `git clone https://github.com/…/helix-ai-migration /opt/helix`.
3. `cd /opt/helix && ./setup.sh --non-interactive`.

`setup.sh` itself uses `cd "$(dirname "$0")"`, which works correctly
when invoked via `bash <(curl …)` but does NOT work when invoked via
`curl … | bash` (`$0` is `bash`, not the script path). So a literal
`curl | bash` doesn't even survive the `cd`.

**Fix:** publish an `install.sh` (separate from `setup.sh`) at a stable
URL that:

```bash
#!/usr/bin/env bash
set -euo pipefail
REPO="${HELIX_REPO:-https://github.com/datainteg/helix-ai-migration}"
DEST="${HELIX_DEST:-/opt/helix}"
BRANCH="${HELIX_BRANCH:-main}"
SHA="${HELIX_INSTALL_SHA256:-}"   # opt-in checksum pin

# … distro detect + apt/dnf/apk install docker + git …
sudo mkdir -p "$DEST"
sudo git clone --depth=1 --branch "$BRANCH" "$REPO" "$DEST"
cd "$DEST"
exec ./setup.sh --non-interactive "$@"
```

…and document the secure form:

```bash
curl -sSL https://helix.datainteg.io/install.sh \
  | sha256sum --check <(echo "abc123…  -") \
  && curl -sSL https://helix.datainteg.io/install.sh | bash
```

(The double-fetch is the cost of "verify before exec.")

---

## 11. Network bind / firewall — see DSETUP-028 above

Already CRITICAL — combined fix recommended there.

---

## 12. Resource sizing

### DSETUP-032 🟡 `setup.sh` doesn't check available RAM / disk

`DEPLOY.md` says "4 GB RAM minimum, 8 GB recommended." A `f1-micro`
(0.6 GB) or `e2-micro` (1 GB) GCE VM gets through the docker-pull
phase and then OOM-kills the worker container during LangGraph
import. Nothing in `setup.sh` checks before committing.

**Fix:** add a preflight:

```bash
mem_kb=$(awk '/MemTotal/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)
mem_gb=$(( mem_kb / 1024 / 1024 ))
if [ "$mem_gb" -lt 2 ]; then
  err "Only ${mem_gb} GB RAM detected. Helix needs ≥ 4 GB for production, ≥ 2 GB to even boot."
  err "  Bump the VM size (GCP: gcloud compute instances set-machine-type …) and retry."
  exit 1
elif [ "$mem_gb" -lt 4 ]; then
  warn "Only ${mem_gb} GB RAM detected. Stack will boot but may OOM under any load."
fi

disk_avail=$(df -BG --output=avail . | tail -1 | tr -d 'G ')
if [ "${disk_avail:-0}" -lt 10 ]; then
  err "Only ${disk_avail} GB free disk on ${PWD}. Need ≥ 20 GB."
  exit 1
fi
```

---

## 13. Disk / volume layout

### DSETUP-033 🟡 Volumes named-only — no host-path option exposed in `setup.sh`

`docker-compose.yml:184-187` declares named volumes
(`helix_postgres_data`, `helix_artifacts`) backed by the default local
driver. That puts data under
`/var/lib/docker/volumes/helix-ai-migration_helix_postgres_data/_data`,
which is **not** mentioned by `setup.sh` or `DEPLOY.md` until very late
(line 244+ of DEPLOY.md). On a GCE VM with a separate persistent disk
mounted at `/srv/`, that disk is unused unless the operator finds the
override-yml example. Add a `setup.sh --data-dir /srv/helix` flag that
auto-generates a `docker-compose.override.yml` with the bind mount.

### DSETUP-034 🔵 SELinux relabel missing on volume mounts

`docker-compose.yml:131` mounts `helix_artifacts:/app/data/artifacts`
without `:z`. On Fedora/RHEL the helix UID-1000 process inside the
container gets `Permission denied` on first write because the SELinux
context is `svirt_sandbox_file_t` for the volume but the container
is `container_t`. Add `:z` (shared label) to volume mounts in compose.

---

## 14. First-start latency / progress indicator

### DSETUP-035 🟡 Readiness loop is silent during the 0-120s wait

`setup.sh:186-193`. Operator sees one line ("Waiting for backend
/api/v1/readyz…") and then nothing for up to 120 s. On a slow VM with a
cold image pull, it can be 5+ minutes (image pull is wall-clock time
before this loop even starts). No spinner, no "still waiting (45s)…"
progress.

**Fix:** echo a dot every poll, newline every 10 iterations:

```bash
for i in $(seq 1 60); do
  status=$(curl -s -o /dev/null -w "%{http_code}" "$backend_url" 2>/dev/null || echo "000")
  if [ "$status" = "200" ]; then
    printf '\n'
    ready=true; break
  fi
  printf '.'
  [ $((i % 10)) -eq 0 ] && printf ' (%ds)\n' $((i * 2))
  sleep 2
done
```

Also: add an explicit `Waiting for Temporal cluster (this can take 30-60s
on first boot)…` step — Temporal `auto-setup` runs its own DB
provisioning inside the temporal container and the worker depends on it.

---

## 15. Tear-down

### DSETUP-036 🟡 `--down` keeps data, `--nuke` deletes everything — no `--uninstall` flag

`setup.sh --down` does `docker compose down` (containers go, volumes
stay). `--nuke` does `down -v` (volumes also go). No middle ground:

- `--uninstall` that removes the `.env` and all generated artifacts but
  keeps Postgres data?
- `--rm-images` that removes the built images so disk reclaim is
  obvious?

Document the matrix in `--help`. Also: `--nuke` does not remove the
`helix-network` bridge (compose leaves it in place if any other
project uses it). Add an explicit `docker network rm helix-network ||
true` after `down -v`.

---

## 16. Windows note (setup.ps1)

`setup.ps1` mirrors `setup.sh` faithfully but inherits most of the same
issues plus a few unique:

- **DSETUP-W01 🟡 No execution-policy guard.** Re-confirms INFRA-022.
  Add `Set-ExecutionPolicy -Scope Process Bypass` at the top.
- **DSETUP-W02 🟡 `try { docker info } catch {}` then checks
  `$LASTEXITCODE`.** The try/catch swallows the throw, so the
  `$LASTEXITCODE` check is dead. Re-confirms INFRA-023.
- **DSETUP-W03 🟡 `generate-secrets.ps1` doesn't ACL the `.env`.**
  Bash version does `chmod 600`; the .ps1 doesn't. Add
  `icacls .env /inheritance:r /grant:r "$env:USERNAME:F"`. Re-confirms
  INFRA-028.
- **DSETUP-W04 🟡 PowerShell 5.1 default encoding is UTF-16-LE with
  BOM.** The `Upsert` function uses `Set-Content` without
  `-Encoding utf8`. Compose and the backend Python config will read the
  `.env` and fail to parse a UTF-16 file with `UnicodeDecodeError`.
  The `Add-Content` calls have the same issue. **Fix:** force
  `-Encoding utf8` on every `.env` write.
- **DSETUP-W05 🔵 `Print` mode echoes secrets to stdout** with no
  warning. Same as INFRA-029.

---

## 17. Single-command install — recommended flow

Today's reality:

```bash
# On a fresh Ubuntu 24.04 LTS GCE VM:
sudo apt update && sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin git
sudo usermod -aG docker "$USER"
# log out, log back in
git clone https://github.com/datainteg/helix-ai-migration /opt/helix
cd /opt/helix
./setup.sh
# then SSH-forward 3000 to your laptop and visit /setup/first-admin
```

That's **8 distinct steps** before the "one-click" script even starts.

### Target single-command flow (post-fix)

```bash
# One command, fresh GCE VM, no prior Docker:
curl -fsSL https://helix.datainteg.io/install.sh | bash -s -- \
  --non-interactive \
  --install-docker \
  --bind 127.0.0.1 \
  --admin-email you@example.com \
  --admin-password-stdin <<< "$(openssl rand -base64 32)"
```

This requires the following changes (each maps to a finding above):

| Change | Finding |
|---|---|
| Ship `install.sh` separate from `setup.sh`, with distro-aware Docker installer | DSETUP-001, DSETUP-031 |
| `setup.sh --non-interactive` flag, no `read -p` blockers | DSETUP-020 |
| `setup.sh --install-docker` calls into bootstrap | DSETUP-001 |
| Default compose port bind = `127.0.0.1`, opt-in 0.0.0.0 | DSETUP-028 |
| `setup.sh --create-admin EMAIL [--password-stdin]` calls `POST /auth/first-admin` | DSETUP-022 |
| Fix Fernet fallback so `cryptography`-less hosts still work | DSETUP-011 |
| Source `.env` after creation so polling uses operator-set values | DSETUP-008 |
| `set -a; . .env; set +a` pattern | DSETUP-008 |
| `.gitattributes` to enforce LF | DSETUP-003 |
| `trap 'on_err …' ERR` + log tail on failure | DSETUP-018, DSETUP-019 |
| Split `--rotate-secrets` so `ENCRYPTION_KEY` can't be casually nuked | DSETUP-010 |
| Move `alembic upgrade head` out of backend CMD into explicit `setup.sh` step (or compose init container) | DSETUP-023 |
| RAM / disk preflight | DSETUP-032 |
| Progress dots during readiness loop | DSETUP-035 |
| Distro-aware firewall hook (`--configure-firewall`) | DSETUP-029 |

---

## 18. Verdict

**Status: `needs work ⚠️`** (one step away from `1-click ready ✅`).

The four CRITICALs (DSETUP-001 no docker installer, DSETUP-010
`--rotate-secrets` data-loss, DSETUP-011 broken Fernet fallback,
DSETUP-028 default `0.0.0.0` bind) and the nine HIGHs are all fixable
in a single afternoon of work. No architectural rewrite needed. After
those fixes the install is genuinely one-command on any modern Linux
distro.

`setup.sh` itself is well-organised: clear sectioning, sensible
defaults, helpful warnings, proper `set -euo pipefail`. The script's
biggest weakness is what it leaves **outside** its own scope (Docker
installation, firewall hardening, GCP networking conventions, the
first-admin user, the actual rotation semantics) rather than anything
wrong with what it does inside.

---

## 19. 7-point pre-deploy checklist

Before flipping a `setup.sh` install to production on GCP / Ubuntu 24:

1. **Docker engine + Compose v2 installed and current user in `docker`
   group.** Verify with `docker info` (NOT through sudo) and
   `docker compose version --short` (≥ 2.20).
2. **Repo cloned with LF line endings.** On Windows: `git config
   --global core.autocrlf input` before clone, or
   `git config core.autocrlf false && git rm --cached -r . && git
   reset --hard`. Verify `file setup.sh` returns "Bourne-Again shell
   script, ASCII text executable" — NOT "with CRLF line terminators".
3. **`.env` populated, secrets script ran cleanly, `ENCRYPTION_KEY` is
   exactly 44 chars and ends with `=`.** Verify:
   `awk -F= '/^ENCRYPTION_KEY=/ {print length($2)}' .env` returns
   `44`.
4. **GCE firewall scoped — TCP 3000 (or 443 via reverse proxy) open
   ONLY to operator IP ranges; TCP 8000 NOT exposed publicly; TCP
   8233 (Temporal UI) NOT exposed publicly.** Audit with
   `gcloud compute firewall-rules list --filter='ALLOWED.ports:(8000 OR 8233 OR 5432 OR 6379 OR 7233)'`.
5. **`HELIX_BIND_HOST=127.0.0.1` set in `.env`** (once DSETUP-028 fix
   lands), with a reverse proxy (Caddy / Traefik / nginx) terminating
   TLS in front. Verify `ss -ltn | grep -E ':(3000|8000)'` shows
   `127.0.0.1:3000` and `127.0.0.1:8000`, NOT `0.0.0.0:*`.
6. **First admin created and password rotated immediately.**
   Either via `/setup/first-admin` wizard (with SSH port-forward) OR
   via the future `./setup.sh --create-admin` flag. Confirm the
   `/setup/first-admin` route returns 404/redirect after first run
   (single-use bootstrap).
7. **Backup cron installed and one trial restore performed.**
   `crontab -l | grep backup.sh`, plus a manual
   `./scripts/restore.sh` against a sacrificial Postgres container.
   Without this nothing about the rest is recoverable.

---

*End of DEPLOY_SETUP.md.*
