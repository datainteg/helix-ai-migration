FROM python:3.11-slim AS builder

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


FROM python:3.11-slim AS runner

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PATH="/install/bin:$PATH"
ENV PYTHONPATH="/install/lib/python3.11/site-packages:/app"
ENV HELIX_PROJECT_ROOT=/app
ENV BMAD_METHOD_ROOT=/app/agents/bmad/BMAD-METHOD

COPY --from=builder /install /install
COPY backend/ .
COPY agents/ ./agents/
COPY connectors/ ./connectors/
COPY _bmad/ ./_bmad/

RUN adduser --disabled-password --gecos "" --uid 1000 helix \
    && chown -R helix:helix /app
USER 1000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
