import os
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.dependencies import require_admin
from app.core.config import settings

router = APIRouter(tags=["system"])


# Enum-stringly typed status values so OpenAPI lists them.
ComponentStatus = Literal["healthy", "down", "unavailable", "unknown"]


class ComponentHealth(BaseModel):
    component: str
    status: ComponentStatus


class SystemHealth(BaseModel):
    status: Literal["ok", "degraded"]
    components: list[ComponentHealth]


class WorkerStatus(BaseModel):
    workers: list[str]
    status: str


class FailedJobs(BaseModel):
    failed_jobs: list[str]


def _check_redis() -> str:
    from app.core.redis_client import get_redis
    r = get_redis()
    if r is None:
        return "unavailable"
    try:
        r.ping()
        return "healthy"
    except Exception:
        return "down"


def _check_temporal() -> str:
    try:
        import socket
        host, port_str = settings.TEMPORAL_ADDRESS.split(":")
        with socket.create_connection((host, int(port_str)), timeout=2):
            return "healthy"
    except Exception:
        return "unavailable"


@router.get("/system/health", response_model=SystemHealth)
def system_health(user_id: str = Depends(require_admin), db: Session = Depends(get_db)):
    checks: list[ComponentHealth] = []

    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        checks.append(ComponentHealth(component="database", status="healthy"))
    except Exception:
        checks.append(ComponentHealth(component="database", status="down"))

    checks.append(ComponentHealth(component="redis", status=_check_redis()))  # type: ignore[arg-type]
    checks.append(ComponentHealth(component="temporal", status=_check_temporal()))  # type: ignore[arg-type]
    checks.append(ComponentHealth(component="worker", status="unknown"))

    storage_ok = os.path.exists(settings.ARTIFACT_STORAGE_PATH) if settings.ARTIFACT_STORAGE_PATH else False
    checks.append(ComponentHealth(component="artifact_storage", status="healthy" if storage_ok else "unknown"))

    overall: Literal["ok", "degraded"] = "ok" if all(c.status != "down" for c in checks) else "degraded"
    return SystemHealth(status=overall, components=checks)


@router.get("/system/workers", response_model=WorkerStatus)
def worker_status(user_id: str = Depends(require_admin)):
    return WorkerStatus(workers=[], status="no workers connected")


@router.get("/system/failed-jobs", response_model=FailedJobs)
def failed_jobs(user_id: str = Depends(require_admin)):
    return FailedJobs(failed_jobs=[])
