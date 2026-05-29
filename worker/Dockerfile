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
    && mkdir -p /app/_bmad-output \
    && chown -R helix:helix /app
USER 1000

# Healthcheck (W-004): lightweight TCP probe instead of full TLS gRPC connect.
# A full Client.connect() every 30 s spawns a new Python interpreter + gRPC
# handshake (~80-200 ms on cross-AZ GCP).  A raw TCP socket.connect() to port
# 7233 is sub-millisecond and confirms the Temporal frontend is reachable.
#
# start-period=60s: cold import of LangGraph + PydanticAI + all LLM SDKs on an
# e2-medium takes >30 s; 60 s avoids spurious "unhealthy" on first boot (W-010).
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('temporal', 7233))" \
    || exit 1

CMD ["python", "-m", "worker.main"]
