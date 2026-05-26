FROM python:3.11-slim-bookworm AS builder

WORKDIR /build

# Install from the lockfile for reproducible builds. Falls back to
# requirements.txt only if the lock is missing (e.g. fresh fork before
# `scripts/lock-requirements.sh` has been run).
COPY backend/requirements.txt backend/requirements.lock* ./
RUN if [ -f requirements.lock ]; then \
        pip install --no-cache-dir --prefix=/install -r requirements.lock ; \
    else \
        echo "WARNING: requirements.lock missing — installing from requirements.txt (non-reproducible)" ; \
        pip install --no-cache-dir --prefix=/install -r requirements.txt ; \
    fi


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
    && chown -R helix:helix /app
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
