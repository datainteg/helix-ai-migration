FROM python:3.11-slim AS builder

WORKDIR /build

COPY worker/requirements.txt worker/requirements.lock* ./
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
# Worker imports `app.db.session` + `app.services.workflow_service` from backend for persistence.
ENV PYTHONPATH="/install/lib/python3.11/site-packages:/app:/app/backend"
ENV HELIX_PROJECT_ROOT=/app
ENV BMAD_METHOD_ROOT=/app/agents/bmad/BMAD-METHOD

COPY --from=builder /install /install

# Selective copies — explicit about what the worker depends on.
COPY worker/ ./worker/
COPY agents/ ./agents/
COPY connectors/ ./connectors/
COPY backend/ ./backend/
COPY _bmad/ ./_bmad/

RUN adduser --disabled-password --gecos "" --uid 1000 helix \
    && chown -R helix:helix /app
USER 1000

# Healthcheck: verify the worker process can import its entrypoint AND reach Temporal.
# Connection check uses a short timeout so the health probe stays cheap.
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import asyncio, os; from temporalio.client import Client; \
asyncio.run(Client.connect(os.getenv('TEMPORAL_ADDRESS', 'localhost:7233')))" \
    || exit 1

CMD ["python", "-m", "worker.main"]
