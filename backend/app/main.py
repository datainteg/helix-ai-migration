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
from app.api.agents import router as agents_router
from app.api.agent_workflows import router as workflows_router
from app.api.artifacts import router as artifacts_router
from app.api.code_reviews import router as code_reviews_router
from app.api.code_conversion import router as conversion_router
from app.api.validation import router as validation_router
from app.api.audit import router as audit_router
from app.api.system import router as system_router
from app.api.connectors import router as connectors_router
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


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

app.include_router(health_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(llm_router, prefix="/api/v1")
app.include_router(projects_router, prefix="/api/v1")
app.include_router(agents_router, prefix="/api/v1")
app.include_router(workflows_router, prefix="/api/v1")
app.include_router(artifacts_router, prefix="/api/v1")
app.include_router(code_reviews_router, prefix="/api/v1")
app.include_router(conversion_router, prefix="/api/v1")
app.include_router(validation_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
app.include_router(system_router, prefix="/api/v1")
app.include_router(connectors_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"name": settings.APP_NAME, "version": "0.1.0", "status": "running"}
