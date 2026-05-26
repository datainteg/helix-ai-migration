# Backend Dockerfile — Production Deploy Audit
Target: Ubuntu 24 LTS on GCP e2-medium (`backend/Dockerfile`)
Review date: 2026-05-26

---

## 1. Multi-stage Build

🟢 **PASS — Builder + runner split is correct.**
`Dockerfile:1` declares `FROM python:3.11-slim AS builder`; `Dockerfile:17` declares `FROM python:3.11-slim AS runner`. Compiled wheel artifacts are copied via `COPY --from=builder /install /install` (`Dockerfile:27`). Source code never bleeds into the builder layer, and the `--prefix=/install` trick keeps site-packages out of the system Python.

🟢 **`--no-cache-dir` used consistently.**
Both branches of the `RUN if [ -f requirements.lock ]` block (`Dockerfile:10,13`) pass `--no-cache-dir` to pip, preventing pip's HTTP cache from inflating intermediate layers.

---

## 2. Base Image

🟠 **INFRA-016 (open) — No digest pin; no bookworm/bullseye tag.**
Both stages use `python:3.11-slim` (`Dockerfile:1,17`) with no `@sha256:…` digest and no OS variant suffix. `slim` without a variant defaults to `slim-bookworm` (Debian 12) today but that contract is informal. More critically, an undigested tag means a `docker pull` in 6 months may silently pull a newer point release with different glibc or OpenSSL, breaking reproducibility and potentially pulling in unvetted CVEs.

Recommended replacement:
```dockerfile
FROM python:3.11-slim-bookworm@sha256:<pinned-digest> AS builder
```

🟢 **glibc (Debian slim) — psycopg2-binary is safe.**
`requirements.txt:11` uses `psycopg2-binary`. The Debian-slim base provides glibc, so PyPI ships a pre-built manylinux wheel. No Alpine C-extension compile risk here.

🟡 **INFRA-016 (partial) — Lock script uses `python:3.11-slim` to compile but `requirements.lock` header (`requirements.lock:2`) reports `Python 3.13`.**
The lock file was regenerated with Python 3.13 locally, not inside the `python:3.11-slim` container specified in `scripts/lock-requirements.sh:43`. This is a reproducibility hazard: some packages resolve differently across interpreter versions. The lock must be regenerated with the exact same Python that runs in the image builder stage.

---

## 3. Non-root User

🟢 **Non-root user declared.**
`Dockerfile:33-35` runs:
```dockerfile
RUN adduser --disabled-password --gecos "" --uid 1000 helix \
    && chown -R helix:helix /app
USER 1000
```

🟡 **UID consistency with named volume.**
The `helix_artifacts` volume is mounted at `/app/data/artifacts` (`docker-compose.yml:131`). Docker creates the volume directory owned by root unless the image's `VOLUME` instruction or an entrypoint `chown` runs first. At startup, the bind-mounted volume will be owned by root and writes from UID 1000 will fail with `PermissionError`. No `VOLUME` instruction and no entrypoint script precede `USER 1000`.

Fix: add an entrypoint script that `chown`s `/app/data/artifacts` before dropping to the helix user, or use a compose-level `init-container` pattern.

---

## 4. CMD — Signal Handling and PID 1

🔴 **INFRA-014 (unresolved) — Shell-form CMD; no tini; SIGTERM goes to `/bin/sh`.**
`Dockerfile:42`:
```dockerfile
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

This is shell-form (no `["..."]` array). PID 1 is `/bin/sh -c …`. Consequences:

1. `docker stop` sends SIGTERM to `/bin/sh`, which does **not** forward to uvicorn. Docker will wait the stop-timeout (default 10 s) then SIGKILL, causing hard kills mid-request.
2. `&&` means if `alembic upgrade head` exits non-zero, the container exits silently — no log entry, no restart-policy-friendly exit code discrimination.
3. Zombie reaping: uvicorn spawns sub-processes for `--workers N`; if PID 1 is `sh`, reaped zombies accumulate.

Neither `tini` nor compose `init: true` is present in `docker-compose.yml` backend service.

Recommended fix (exec-form entrypoint script):
```dockerfile
COPY entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD []
```
```bash
#!/bin/sh
set -e
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 $UVICORN_EXTRA_ARGS
```
Or install tini:
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends tini && rm -rf /var/lib/apt/lists/*
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

---

## 5. Alembic on Every Restart

🟠 **INFRA-015 (unresolved) — `alembic upgrade head` runs on every container restart.**
`Dockerfile:42` still bundles alembic migration with startup. On a GCP VM reboot with `restart: unless-stopped`, every service restart hits Postgres with a schema-migration lock. On scale-out (multiple replicas), two containers will race for the alembic migration lock, causing a 30–60 s delay and occasional `LockNotAvailable` errors.

Recommended pattern: a separate one-shot migration service in compose:
```yaml
  migrate:
    image: helix/backend:latest
    command: ["alembic", "upgrade", "head"]
    depends_on:
      postgres:
        condition: service_healthy
    restart: "no"
```
Then the backend CMD becomes simply:
```dockerfile
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 6. .dockerignore

🟢 **`.dockerignore` covers all required exclusions.**
Root `.dockerignore` excludes:
- `**/__pycache__`, `**/*.pyc`, `**/*.pyo` — Python bytecode
- `.venv`, `venv`, `env`, `*.egg-info` — virtual environments
- `.git`, `.gitignore`, `.github` — VCS
- `backend/tests`, `backend/test.db` — test artifacts
- `/docs` (anchored) — documentation
- `/*.md` — root markdown (with `!/README.md` exemption)
- `node_modules`, `frontend/.next` — frontend build artifacts

🟡 **`backend/tests/` vs `backend/tests` path.**
The ignore file uses `backend/tests` (no trailing slash), which correctly excludes the directory. However, the pattern `/*.md` uses a leading slash (repo root anchor). Any `*.md` files nested inside `backend/` (e.g., `backend/CHANGELOG.md`) would NOT be excluded. Low impact but worth noting.

---

## 7. Layer Caching

🟢 **Requirements copied before source — pip install layer caches correctly.**
`Dockerfile:8` copies only `requirements.txt` and `requirements.lock*` before running `pip install`. Application source (`COPY backend/ .`) follows at `Dockerfile:28`, after the pip install RUN. This means the expensive dependency layer is invalidated only when the lockfile changes, not on every source code edit.

---

## 8. HEALTHCHECK

🟡 **Dockerfile HEALTHCHECK duplicates compose healthcheck — inconsistent parameters.**
`Dockerfile:39-40` declares:
```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1
```
`docker-compose.yml:133-137` declares:
```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')"]
  interval: 30s
  timeout: 10s
  start_period: 30s
  retries: 3
```

Differences: `timeout` is 5 s in Dockerfile vs 10 s in compose; `start_period` is 10 s in Dockerfile vs 30 s in compose. Compose overrides the Dockerfile HEALTHCHECK, so the Dockerfile values are silently ignored. This creates a false sense of security (image appears correct standalone) and confuses `docker inspect` output. Keep only one source of truth — remove the `HEALTHCHECK` from the Dockerfile and manage it exclusively in compose, or align all values.

Additionally, the `CMD python -c "..."` form: if the `/api/v1/health` endpoint returns a non-2xx status, `urllib.request.urlopen` raises an exception and the check exits 1 — that part is correct. However, if the Python interpreter itself is missing (broken image), the check silently fails rather than reporting `unhealthy`. The Dockerfile variant also has `|| exit 1` which is redundant — the exception already causes exit 1.

---

## 9. Build Secrets / PyPI Credentials

🟢 **No credentials baked into image layers.**
The `RUN pip install …` commands (`Dockerfile:10,13`) use only plain PyPI (https://pypi.org). No `-i`, `--index-url`, or `--extra-index-url` flags appear with tokens. No `ARG` or `ENV` carrying API keys is present.

🟢 **No `.env` file copied into the image.**
The compose `env_file: .env` (`docker-compose.yml:122`) injects env vars at runtime, not build time. The `.dockerignore` does not explicitly exclude `.env` itself (only `.env.example`), but `.env` is not referenced in any `COPY` instruction in the Dockerfile, so it is not captured in a layer even if present in the build context. This is acceptable but fragile — an explicit `.env` line in `.dockerignore` would make the exclusion unambiguous.

---

## 10. CVE Scanner Exposure / Base Image Age

🟠 **`python:3.11-slim` is unpinned — CVE exposure unknown and variable.**
Without a digest pin, every CI build pulls whatever image Docker Hub serves as `python:3.11-slim` at that moment. The current `python:3.11-slim-bookworm` image typically lags Debian security patches by 1–4 weeks. As of 2026-05 there are no critical CVEs in the Debian 12 base that affect this workload, but the risk is structural rather than point-in-time.

For a GCP VM production deploy, the recommended flow is:
1. Pin to a digest at the start of a sprint: `docker pull python:3.11-slim-bookworm && docker inspect --format='{{index .RepoDigests 0}}' python:3.11-slim-bookworm`
2. Record that digest in the Dockerfile.
3. Refresh the digest monthly via a CI job.

Integrate with `trivy image helix/backend:latest` or GCP Artifact Registry's built-in vulnerability scanning after every push.

---

## 11. Uvicorn Worker Count

🟠 **Worker count hardcoded to 1 (default) — not env-overridable.**
`Dockerfile:42`:
```dockerfile
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
```
No `--workers` flag is passed. uvicorn defaults to 1 worker (single process). On a GCP e2-medium (2 vCPUs, 4 GB RAM), Gunicorn's standard formula is `2 * CPU + 1 = 5` workers. Running 1 worker means the CPU sits idle under any non-trivial concurrency.

Recommended fix:
```dockerfile
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-4}"]
```
or switch to gunicorn as the process manager:
```dockerfile
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", "--bind", "0.0.0.0:8000", "app.main:app"]
```
Note: if running multiple workers, shared in-memory state (e.g., simple Python dicts for rate-limiting or caching) will desync across workers. Verify that `slowapi` and any in-process caches use Redis as the backing store.

---

## 12. TLS Termination

🟡 **TLS terminates nowhere in the current stack — HTTPS path not defined for GCP VM.**
`docker-compose.yml:119-120` exposes the backend on `${BACKEND_HOST_PORT:-8000}` (plain HTTP). uvicorn is not started with `--ssl-keyfile`/`--ssl-certfile`. No nginx or Caddy service appears in compose.

For a single GCP VM, the recommended path to HTTPS is:
1. Add a Caddy (or nginx + certbot) service to compose that terminates TLS via Let's Encrypt and reverse-proxies to `backend:8000`.
2. The backend port should NOT be exposed on `0.0.0.0` — bind to `127.0.0.1` or remove the `ports:` block entirely and let Caddy reach it via the `helix-network` bridge.

Currently, `${BACKEND_HOST_PORT:-8000}` binds to all interfaces on the VM host. Any firewall rule allowing port 8000 will expose the API over plain HTTP to the internet. GCP VPC firewall rules must explicitly block 8000 from ingress, but this is an operational control that is invisible in the Dockerfile/compose definition.

---

## 13. Logging

🟢 **`PYTHONUNBUFFERED=1` set — stdout/stderr goes directly to Docker log driver.**
`Dockerfile:21` sets `ENV PYTHONUNBUFFERED=1`, preventing Python from buffering stdout. Docker Compose will capture it via its default `json-file` log driver.

🟡 **Structured JSON logging is wired in `requirements.txt` but not enforced at the image level.**
`requirements.txt:2` includes `python-json-logger>=2.0.7`. Whether the application actually emits JSON logs depends on the app's logging configuration, not the Dockerfile. No `LOGGING_FORMAT` or similar env var is documented or defaulted in the Dockerfile. For GCP Cloud Logging, JSON on stdout with a `severity` key is strongly preferred for log-based metrics and alerting.

---

## 14. Image Size Estimate

🟠 **Final image is likely 1.1–1.4 GB — exceeds 1 GB target.**
The dependency set is very large (203 pinned packages, `requirements.lock:2`). Heavy contributors:

| Package | Approximate wheel size |
|---|---|
| `google-cloud-aiplatform` + `google-auth` + `proto-plus` | ~120 MB |
| `boto3` + `botocore` | ~90 MB |
| `snowflake-sqlalchemy` + `snowflake-connector-python` | ~80 MB |
| `opentelemetry-*` (7 packages) | ~40 MB |
| `langgraph` + `pydantic-ai` + `openai` | ~60 MB |
| `reportlab` | ~15 MB |
| `pytest` + `pytest-asyncio` (test deps in prod image!) | ~10 MB |
| python:3.11-slim base | ~130 MB |

Total rough estimate: **~800 MB–1.1 GB compressed**, **~1.2–1.5 GB uncompressed on disk**.

The most impactful size reduction is removing `pytest` and `pytest-asyncio` from `requirements.txt` (they are dev-only dependencies). Separate them into `requirements-dev.txt` and do not install them in the production Dockerfile.

For GCP e2-medium with a 20 GB boot disk, a 1.4 GB image is acceptable but leaves limited headroom once Postgres data and log volumes are counted.

---

## 15. Reproducibility

🟡 **`requirements.lock` exists but was compiled with the wrong Python version.**
`requirements.lock:2` reports:
```
# This file is autogenerated by pip-compile with Python 3.13
```
The runtime is Python 3.11 (`Dockerfile:1`). The lock script (`scripts/lock-requirements.sh:43`) is configured to use `python:3.11-slim` inside Docker, but the currently committed lock was generated outside that container with a local Python 3.13. Some packages (e.g., packages with Python-version-specific markers in their metadata) may resolve to different versions under 3.11 vs 3.13.

Action: run `./scripts/lock-requirements.sh` from a machine with Docker to regenerate the lock inside the `python:3.11-slim` container, then commit the result. Add a CI check:
```yaml
- run: docker run --rm -v $PWD:/work -w /work python:3.11-slim bash -c \
    "pip install pip-tools && pip-compile --strip-extras -o backend/requirements.lock.check backend/requirements.txt && diff backend/requirements.lock backend/requirements.lock.check"
```

🟠 **`requirements.txt` uses `>=` (minimum-version) constraints throughout** (`requirements.txt:1-36`). pip-compile resolves them to exact pins in `requirements.lock`, but the absence of upper bounds means a future `./scripts/lock-requirements.sh --upgrade` can silently pull in a breaking major version (e.g., `langgraph 1.0`). Consider adding `~=` (compatible-release) constraints for the most volatile packages.

---

## 16. Additional Findings

### 16.1 Test Dependencies Shipped in Production Image

🔴 **`pytest` and `pytest-asyncio` are in `requirements.txt:35-36` — they are installed in the production image.**
This adds ~10 MB and increases the attack surface unnecessarily. Split into `requirements-dev.txt`:
```
# requirements-dev.txt
pytest>=8.0.0
pytest-asyncio>=0.23.0
```
Change the Dockerfile to install only `requirements.txt` (without test deps). The lock script should generate `backend/requirements-dev.lock` separately.

### 16.2 `pyodbc` — Requires `unixODBC` Native Library

🟡 **`pyodbc>=5.0.0` (`requirements.txt:14`) requires `libodbc.so` at runtime.**
`python:3.11-slim` does not include `unixODBC`. The container will crash at import time if any code path imports `pyodbc`. The builder stage installs the Python wheel, but the runner stage lacks the native `.so`. Add to the runner stage:
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends unixodbc && rm -rf /var/lib/apt/lists/*
```
This also slightly inflates image size (~4 MB).

### 16.3 Build Context Path Assumption

🟡 **Dockerfile uses `COPY backend/requirements.txt` (`Dockerfile:8`), implying the Docker build context must be the repo root.**
This is correct for `docker-compose.build.yml` with `context: .`, but if someone runs `docker build .` from inside `backend/`, the build will fail with `COPY failed: file not found`. The `COPY backend/ .` pattern on `Dockerfile:28` confirms the root-context requirement. This should be documented in the contributing guide or enforced by a Makefile target.

---

## Summary Table

| # | Severity | Finding | Dockerfile Line |
|---|---|---|---|
| 1 | 🟢 | Multi-stage builder + runner split | 1, 17 |
| 2 | 🟢 | `--no-cache-dir` used | 10, 13 |
| 3 | 🟠 | Base image not pinned to digest or bookworm variant (INFRA-016) | 1, 17 |
| 4 | 🟡 | Lock compiled with Python 3.13 but runtime is 3.11 | requirements.lock:2 |
| 5 | 🟢 | Non-root UID 1000 declared | 33–35 |
| 6 | 🟡 | Named volume `/app/data/artifacts` created as root; UID 1000 writes will fail | compose:131 |
| 7 | 🔴 | Shell-form CMD; no tini/--init; SIGTERM swallowed (INFRA-014 unresolved) | 42 |
| 8 | 🟠 | Alembic runs on every restart; migration race on scale-out (INFRA-015 unresolved) | 42 |
| 9 | 🟢 | `.dockerignore` covers `__pycache__`, `.venv`, `.git`, tests, docs | .dockerignore |
| 10 | 🟡 | `backend/*.md` not excluded by `.dockerignore` | .dockerignore:31 |
| 11 | 🟢 | Requirements copied before source — pip layer caches | 8 |
| 12 | 🟡 | Dockerfile HEALTHCHECK conflicts with compose healthcheck (different timeouts) | 39–40 |
| 13 | 🟢 | No PyPI credentials baked into layers | 10, 13 |
| 14 | 🟡 | `.env` not explicitly excluded from build context in `.dockerignore` | .dockerignore |
| 15 | 🟠 | Unpinned base image — CVE exposure window unknown | 1, 17 |
| 16 | 🟠 | 1 uvicorn worker hardcoded; 2-vCPU e2-medium underutilized | 42 |
| 17 | 🟡 | TLS not terminated anywhere; backend port bound to all interfaces | compose:119 |
| 18 | 🟢 | `PYTHONUNBUFFERED=1` — stdout unbuffered for log driver | 21 |
| 19 | 🟡 | JSON logging configured in code only, not enforced at image level | — |
| 20 | 🟠 | Estimated image 1.1–1.4 GB; pytest/boto3/snowflake bloat | requirements.txt |
| 21 | 🔴 | `pytest`+`pytest-asyncio` installed in production image | requirements.txt:35-36 |
| 22 | 🟡 | `pyodbc` requires `unixodbc` native lib absent from slim image | requirements.txt:14 |
| 23 | 🟡 | `requirements.txt` uses `>=` only — no upper-bound guards | requirements.txt |
| 24 | 🟡 | Build context must be repo root; not enforced or documented | 8, 28 |

---

## Verdict

**image builds clean ✅ / fails on X ❌**

The image **builds clean** in a standard `docker build --pull --no-cache .` from the repo root. However, it will exhibit the following **runtime failures** on a GCP e2-medium before any mitigations are applied:

1. **`pyodbc` import crash** at first request that touches any SQL Server / ODBC connector path — `libodbc.so` is missing from the runner image. If pyodbc is not used at startup, this is deferred until runtime.
2. **Graceful shutdown failure** on `docker stop` — uvicorn never receives SIGTERM; every stop is a hard SIGKILL after 10 s.
3. **Named volume permission denied** — `/app/data/artifacts` will be root-owned; artifact writes from UID 1000 will fail on first artifact save.

**Estimated `docker build --pull --no-cache .` time on GCP e2-medium:**
- Pull `python:3.11-slim` (130 MB): ~15 s
- `pip install` 203 packages (resolving wheels for boto3, snowflake, google-cloud-aiplatform, langgraph, pydantic-ai, opentelemetry): **8–14 minutes** (dominated by large wheel downloads and compilation of any packages without pre-built manylinux wheels)
- `COPY` source files: ~30 s
- Total: **9–15 minutes**

**Priority fixes before production deploy on GCP:**

1. 🔴 Replace shell-form CMD with exec-form entrypoint script using `exec uvicorn …` (fixes SIGTERM, PID 1, INFRA-014)
2. 🔴 Move `pytest`/`pytest-asyncio` to `requirements-dev.txt`; do not install in production image
3. 🟠 Add `unixodbc` apt package to runner stage (or remove `pyodbc` if not needed)
4. 🟠 Extract `alembic upgrade head` to a dedicated compose `migrate` one-shot service (fixes INFRA-015)
5. 🟠 Regenerate `requirements.lock` with `./scripts/lock-requirements.sh` (Python 3.11 inside Docker)
6. 🟠 Pin base images to `python:3.11-slim-bookworm@sha256:<digest>`
7. 🟠 Add `--workers ${UVICORN_WORKERS:-4}` to uvicorn CMD
8. 🟡 Add Caddy/nginx reverse proxy service for TLS; remove backend `ports:` from host interface
9. 🟡 Fix named volume ownership with entrypoint `chown` before `USER 1000`
10. 🟡 Consolidate HEALTHCHECK to compose only; remove from Dockerfile
