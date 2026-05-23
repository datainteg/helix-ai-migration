FROM python:3.11-slim AS builder

WORKDIR /build

COPY worker/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


FROM python:3.11-slim AS runner

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PATH="/install/bin:$PATH"
ENV PYTHONPATH="/install/lib/python3.11/site-packages:/app:/app/backend"

COPY --from=builder /install /install
COPY . .

RUN adduser --disabled-password --gecos "" --uid 1000 helix \
    && chown -R helix:helix /app
USER 1000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

CMD ["python", "-m", "worker.main"]
