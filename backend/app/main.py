from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

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
from app.core.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.get("/")
async def root():
    return {"name": settings.APP_NAME, "version": "0.1.0", "status": "running"}
