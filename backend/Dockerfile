FROM python:3.11-slim-bookworm AS builder

WORKDIR /build

# SC-055: install ONLY from the lockfile for reproducible, supply-chain-safe
# builds. Previously a missing requirements.lock fell back to requirements.txt
# with a WARNING — the build silently proceeded with whatever transitive
# versions PyPI returned, defeating pinning. Now we FAIL CLOSED: the build
# aborts if requirements.lock is absent. Generate it with
# `scripts/lock-requirements.sh` before building.
COPY backend/requirements.txt backend/requirements.lock* ./
RUN test -f requirements.lock || { \
        echo "ERROR: requirements.lock missing — refusing non-reproducible build. Run scripts/lock-requirements.sh first." >&2 ; \
        exit 1 ; \
    } \
    && pip install --no-cache-dir --prefix=/install -r requirements.lock


FROM python:3.11-slim-bookworm AS runner

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PATH="/install/bin:$PATH"
ENV PYTHONPATH="/install/lib/python3.11/site-packages:/app"
ENV HELIX_PROJECT_ROOT=/app
ENV BMAD_METHOD_ROOT=/app/agents/bmad/BMAD-METHOD

# unixodbc: required by the pyodbc wheel used in connectors/sqlserver.
# libodbc2 is the Debian 12 (bookworm) package name for the shared library.
RUN apt-get update \
    && apt-get install -y --no-install-recommends unixodbc libodbc2 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /install
COPY backend/ .
COPY agents/ ./agents/
COPY connectors/ ./connectors/
COPY _bmad/ ./_bmad/

RUN adduser --disabled-password --gecos "" --uid 1000 helix \
    && mkdir -p /app/data/artifacts \
    && chown -R helix:helix /app
# Pre-creating /app/data/artifacts as helix means a freshly-created named volume
# mounted there inherits helix ownership — so the app (uid 1000) can write
# generated/uploaded artifacts. Without this the empty volume comes up root-owned
# and every artifact write fails with EACCES.
USER 1000

EXPOSE 8000

# Align with docker-compose.yml healthcheck: interval=30s, timeout=10s,
# start_period=30s, retries=3.
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

# exec-form ENTRYPOINT — PID 1 is uvicorn, not sh.
# SIGTERM from `docker stop` is forwarded directly to uvicorn for graceful shutdown.
# Alembic migrations are handled by the separate `backend-migrate` compose service (F2).
# UVICORN_WORKERS defaults to 2 (safe for e2-medium 2-vCPU); override via env.
ENTRYPOINT ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-2}"]
