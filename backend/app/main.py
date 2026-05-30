from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.rate_limiting import limiter
from app.core.logging_config import configure_logging, RequestIdMiddleware
from app.utils.idempotency import IdempotencyMiddleware
from app.utils.rate_limit_handler import rate_limit_exceeded_handler
from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.llm_providers import router as llm_router
from app.api.projects import router as projects_router
from app.api.agent_workflows import router as workflows_router
from app.api.artifacts import router as artifacts_router
from app.api.code_reviews import router as code_reviews_router
from app.api.validation import router as validation_router
from app.api.audit import router as audit_router
from app.api.system import router as system_router
from app.api.connectors import router as connectors_router
from app.api.encryption import router as encryption_router
from app.api.invitations import router as invitations_router
from app.api.webhooks import router as webhooks_router
from app.api.usage import router as usage_router
from app.api.superadmin import router as superadmin_router
from app.api.users import router as users_router
from app.api.sprints import router as sprints_router
from app.api.dashboard import router as dashboard_router
from app.api.cutovers import router as cutovers_router
from app.api.migration_templates import router as templates_router
from app.api.integrations import router as integrations_router
from app.api.compliance import router as compliance_router
from app.api.schema_drift import router as schema_drift_router
from app.api.cdc import router as cdc_router
from app.api.workflow_ops import router as workflow_ops_router
from app.api.marketplace import router as marketplace_router
from app.api.knowledge import router as knowledge_router
from app.api.migrations import router as migrations_router
from app.core.config import settings

configure_logging(settings.APP_ENV)

if settings.SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.APP_ENV,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        traces_sample_rate=0.2,
    )

# OpenTelemetry setup — optional dep. The opentelemetry-* packages aren't in
# the base requirements; pylance warns about unresolved imports, but the block
# only runs when OTEL_ENDPOINT is set AND a try/except around the package
# imports keeps a missing dep from crashing boot.
if settings.OTEL_ENDPOINT:
    try:
        from opentelemetry import trace  # type: ignore[import-not-found]
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore[import-not-found]
        from opentelemetry.sdk.trace.export import BatchSpanProcessor  # type: ignore[import-not-found]
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter  # type: ignore[import-not-found]
        from opentelemetry.sdk.resources import Resource  # type: ignore[import-not-found]
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor  # type: ignore[import-not-found]

        resource = Resource.create({"service.name": settings.APP_NAME, "deployment.environment": settings.APP_ENV})
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.OTEL_ENDPOINT)))
        trace.set_tracer_provider(provider)
        SQLAlchemyInstrumentor().instrument()
    except ImportError:
        import logging
        logging.getLogger(__name__).warning(
            "OTEL_ENDPOINT set but opentelemetry packages not installed; skipping tracing setup."
        )

def _start_cdc_engine() -> None:
    """Boot the CDC polling loop. No-op when HELIX_CDC_DISABLED is set."""
    try:
        from app.services.cdc_engine import start as start_cdc
        start_cdc()
    except Exception as exc:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).warning("CDC engine failed to start: %s", exc)


def _check_first_admin_bootstrap() -> None:
    """SC-011: tell the operator the SETUP_TOKEN they need to mint the first
    admin. Runs once at boot; harmless to re-emit if the backend restarts
    while still un-bootstrapped.
    """
    import logging as _logging
    import sys as _sys
    _log = _logging.getLogger(__name__)
    try:
        from app.db.session import SessionLocal
        from app.models.identity import User
        db = SessionLocal()
        try:
            already = db.query(User).filter(User.is_super_admin == True).first()
        finally:
            db.close()
        if already:
            return
        if not settings.SETUP_TOKEN:
            msg = (
                "SETUP_TOKEN is not configured but no super_admin exists yet. "
                "POST /auth/first-admin will reject all callers until you set "
                "SETUP_TOKEN=<random hex> in the backend environment."
            )
        else:
            msg = (
                "No super_admin exists yet. POST /auth/first-admin must be "
                "called with header X-Setup-Token: <value of SETUP_TOKEN>."
            )
        _log.critical(msg)
        # Also print to stderr so it shows up in docker logs even when
        # logging filters are misconfigured.
        try:
            print(f"[helix] {msg}", file=_sys.stderr, flush=True)
        except Exception:
            pass
    except Exception as exc:  # noqa: BLE001 — never block boot on this advice
        _log.debug("first-admin bootstrap check skipped: %s", exc)


def _stop_cdc_engine() -> None:
    try:
        from app.services.cdc_engine import stop as stop_cdc
        stop_cdc()
    except Exception:  # noqa: BLE001
        pass


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """L-004: FastAPI `lifespan` replaces the deprecated `@app.on_event`
    startup/shutdown handlers (Starlette removed on_event in newer releases).
    Startup boots the CDC engine + emits the first-admin bootstrap advice;
    shutdown stops the CDC poll loop.
    """
    _start_cdc_engine()
    _check_first_admin_bootstrap()
    try:
        yield
    finally:
        _stop_cdc_engine()


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.state.limiter = limiter
# Use our own 429 handler so the body matches the FastAPI-standard
# `{detail, retry_after_seconds}` envelope and a `Retry-After` header is
# always set. Replaces slowapi's default `{"error": "..."}` body which
# diverged from every other error in the API (see REVIEW_API_CONTRACT
# `Cross-cutting: Rate-limit responses`).
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_middleware(RequestIdMiddleware)
# IdempotencyMiddleware stashes the `Idempotency-Key` header on
# `request.state.idempotency_key`. The actual cache lookup lives in
# `@idempotent("...")` decorators on the few POST handlers that mutate
# expensive state. The middleware alone is cheap (one header read +
# attribute set per request).
app.add_middleware(IdempotencyMiddleware)

_MAX_BODY_BYTES = (settings.MAX_UPLOAD_MB + 1) * 1024 * 1024


@app.middleware("http")
async def enforce_body_size(request: Request, call_next):
    """Reject oversized requests up front.

    Checks Content-Length (cheap, catches well-behaved clients) AND the raw
    incoming body length AFTER buffering (catches chunked uploads that omit
    Content-Length). For multipart uploads the per-file validation in
    storage/local.py still applies on top of this.
    """
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > _MAX_BODY_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={"detail": f"Request body exceeds {settings.MAX_UPLOAD_MB + 1} MB limit"},
                )
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length header"})
    return await call_next(request)


# Paths a demo session may still POST to (auth lifecycle only).
_DEMO_WRITE_ALLOWLIST = {
    "/api/v1/auth/logout",
    "/api/v1/auth/demo-login",
    "/api/v1/auth/sse-ticket",
}


@app.middleware("http")
async def enforce_demo_readonly(request: Request, call_next):
    """Read-only demo: 403 any mutating request that carries a demo token.

    The "Login with Demo User" token carries an `is_demo` claim. Per-endpoint
    permission gates are inconsistent, so this is the single guarantee that a
    shared demo session can never mutate data (which would corrupt the sandbox
    for other demo users). Real users are unaffected — their tokens lack the
    claim. Reads (GET/HEAD/OPTIONS) always pass.
    """
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.url.path not in _DEMO_WRITE_ALLOWLIST:
        from app.auth.jwt import AUTH_COOKIE_NAME, decode_access_token

        token = request.cookies.get(AUTH_COOKIE_NAME)
        if not token:
            auth = request.headers.get("authorization", "")
            if auth.lower().startswith("bearer "):
                token = auth[7:]
        if token:
            try:
                payload = decode_access_token(token)
            except Exception:  # noqa: BLE001 — invalid token; let the route's auth handle it
                payload = None
            if payload and payload.get("is_demo"):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Read-only demo session — sign in with a real account to make changes."},
                )
    return await call_next(request)


@app.middleware("http")
async def guard_metrics_endpoint(request: Request, call_next):
    """SC-056: require a static bearer on the backend `/metrics` route when
    METRICS_TOKEN is set.

    Caddy already returns 403 for `/metrics`, but the backend still serves it on
    :8000 — anyone bypassing Caddy (SSH tunnel, misconfigured firewall) could
    scrape full Prometheus metrics (paths, latencies, tenant labels). When
    METRICS_TOKEN is configured the scraper must send
    `Authorization: Bearer <METRICS_TOKEN>`; an empty token keeps the prior
    behaviour (open on the backend port, blocked at Caddy only).
    """
    if request.url.path == "/metrics" and settings.METRICS_TOKEN:
        import hmac as _hmac
        auth = request.headers.get("authorization", "")
        expected = f"Bearer {settings.METRICS_TOKEN}"
        if not auth or not _hmac.compare_digest(auth, expected):
            return JSONResponse(status_code=401, content={"detail": "metrics access requires a valid bearer token"})
    return await call_next(request)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Inject defensive HTTP response headers.

    These are cheap, broadly applicable, and reject classes of attacks even
    when application code has bugs: MIME-sniffing (XCTO), clickjacking
    (XFO), and Referer leaks. CSP is not enforced here because endpoints
    serve API JSON, not HTML — the frontend ships its own CSP.
    """
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    # SC-057: emit HSTS whenever the request is served over HTTPS — not only
    # when APP_ENV=production. A staging/preview deploy on https was
    # previously SSL-strippable because it lacked the header. `X-Forwarded-Proto`
    # (set by Caddy) is reflected into `request.url.scheme` by Starlette's
    # ProxyHeaders handling, so this fires correctly behind the proxy.
    if request.url.scheme == "https":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX or None,
    # SC-010 (supersedes SC-035): the API now ALSO authenticates the browser via
    # an HttpOnly `helix_token` cookie. A credentialed cross-origin request that
    # carries that cookie REQUIRES `allow_credentials=True` for the browser to
    # send the cookie and read the response — and the CORS spec forbids pairing
    # `allow_credentials=True` with a wildcard origin, so `allow_origins` /
    # `allow_origin_regex` must stay an EXACT allowlist (never `*`). They are:
    # `settings.CORS_ORIGINS` (production = settings.FRONTEND_URL; config.py
    # rejects `*` and any regex when APP_ENV=production) plus the dev-only
    # localhost regex. SC-035 dropped credentials because the API was then
    # bearer-only; with HttpOnly cookies in use that reasoning no longer holds.
    # The CSRF surface SC-035 worried about is now closed by the cookie's
    # SameSite=Strict attribute, which stops the browser attaching it to any
    # cross-site request.
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    # `Idempotency-Key` lets browsers + SDK consumers opt into POST
    # de-duplication on retries (API-C4). `X-Active-Org-Id` is read by
    # the per-org rate limiter (`rate_limiting._org_key`) — must be on
    # the allow list or the browser strips it before forwarding.
    allow_headers=[
        "Authorization", "Content-Type", "Accept",
        "Idempotency-Key", "X-Active-Org-Id",
        # `X-Setup-Token` carries the first-admin provisioning token from the
        # /setup/first-admin wizard — must be allow-listed or the browser's
        # preflight is rejected (400 Disallowed CORS headers).
        "X-Setup-Token",
    ],
    # Surface the replay marker so SDKs can detect cache hits and the
    # standardized retry hint on 429s.
    expose_headers=["Idempotency-Replayed", "Retry-After"],
)

# SC-040: BREACH-resistant gzip. The stock GZipMiddleware compresses every
# response over `minimum_size`; if a secret and reflected/attacker-influenced
# input ever co-occur in one gzipped body, the compressed length becomes a
# BREACH oracle. We exclude the endpoints whose bodies may carry secrets
# (`/auth/*` returns tokens; `/llm-providers/*` returns provider config) by
# wrapping GZipMiddleware in a path-aware shim that bypasses compression for
# those prefixes and delegates everything else.
class _SelectiveGZipMiddleware(GZipMiddleware):
    """GZipMiddleware that skips compression for secret-bearing path prefixes."""

    _NO_GZIP_PREFIXES = ("/api/v1/auth/", "/api/v1/llm-providers/")

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            path = scope.get("path", "")
            if any(path.startswith(p) for p in self._NO_GZIP_PREFIXES):
                # Hand the request straight to the wrapped ASGI app, bypassing
                # the gzip responder entirely for these routes.
                await self.app(scope, receive, send)
                return
        await super().__call__(scope, receive, send)


app.add_middleware(_SelectiveGZipMiddleware, minimum_size=1000)

# Prometheus metrics at /metrics
try:
    from prometheus_fastapi_instrumentator import Instrumentator  # type: ignore[import-not-found]
    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_respect_env_var=False,
        excluded_handlers=["/metrics", "/docs", "/openapi.json"],
    ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
except ImportError:
    pass

# OpenTelemetry FastAPI instrumentation (must be after app creation)
if settings.OTEL_ENDPOINT:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # type: ignore[import-not-found]
        FastAPIInstrumentor.instrument_app(app)
    except ImportError:
        pass

app.include_router(health_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(llm_router, prefix="/api/v1")
app.include_router(projects_router, prefix="/api/v1")
app.include_router(workflows_router, prefix="/api/v1")
app.include_router(artifacts_router, prefix="/api/v1")
app.include_router(code_reviews_router, prefix="/api/v1")
app.include_router(validation_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
app.include_router(system_router, prefix="/api/v1")
app.include_router(connectors_router, prefix="/api/v1")
app.include_router(encryption_router, prefix="/api/v1")
app.include_router(invitations_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")
app.include_router(usage_router, prefix="/api/v1")
app.include_router(superadmin_router, prefix="/api/v1/superadmin")
app.include_router(users_router, prefix="/api/v1")
app.include_router(sprints_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(cutovers_router, prefix="/api/v1")
app.include_router(templates_router, prefix="/api/v1")
app.include_router(integrations_router, prefix="/api/v1")
app.include_router(compliance_router, prefix="/api/v1")
app.include_router(schema_drift_router, prefix="/api/v1")
app.include_router(cdc_router, prefix="/api/v1")
app.include_router(workflow_ops_router, prefix="/api/v1")
app.include_router(marketplace_router, prefix="/api/v1")
app.include_router(knowledge_router, prefix="/api/v1")
app.include_router(migrations_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"name": settings.APP_NAME, "version": "0.1.0", "status": "running"}
