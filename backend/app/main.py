from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.rate_limiting import limiter
from app.core.logging_config import configure_logging, RequestIdMiddleware
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

# OpenTelemetry setup
if settings.OTEL_ENDPOINT:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    resource = Resource.create({"service.name": settings.APP_NAME, "deployment.environment": settings.APP_ENV})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.OTEL_ENDPOINT)))
    trace.set_tracer_provider(provider)
    SQLAlchemyInstrumentor().instrument()

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_middleware(RequestIdMiddleware)

_MAX_BODY_BYTES = (settings.MAX_UPLOAD_MB + 1) * 1024 * 1024


@app.middleware("http")
async def enforce_body_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > _MAX_BODY_BYTES:
        return JSONResponse(status_code=413, content={"detail": f"Request body exceeds {settings.MAX_UPLOAD_MB + 1} MB limit"})
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
    if settings.APP_ENV == "production":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX or None,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Prometheus metrics at /metrics
try:
    from prometheus_fastapi_instrumentator import Instrumentator
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
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    FastAPIInstrumentor.instrument_app(app)

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
app.include_router(superadmin_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(sprints_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"name": settings.APP_NAME, "version": "0.1.0", "status": "running"}
