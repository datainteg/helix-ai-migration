from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.jwt import get_current_user_id
from app.models.observability import SystemHealthCheck

router = APIRouter(tags=["system"])


@router.get("/system/health")
def system_health(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    checks = []

    # Database
    try:
        db.execute(db.query(SystemHealthCheck).statement.limit(1))
        checks.append({"component": "database", "status": "healthy"})
    except Exception:
        checks.append({"component": "database", "status": "down"})

    # Redis — skip check if not connected
    checks.append({"component": "redis", "status": "unknown"})

    # Temporal
    checks.append({"component": "temporal", "status": "unknown"})

    # Worker
    checks.append({"component": "worker", "status": "unknown"})

    # Artifact storage
    from app.core.config import settings
    import os
    storage_ok = os.path.exists(settings.ARTIFACT_STORAGE_PATH) if settings.ARTIFACT_STORAGE_PATH else False
    checks.append({"component": "artifact_storage", "status": "healthy" if storage_ok else "unknown"})

    return {"status": "ok", "components": checks}


@router.get("/system/workers")
def worker_status(user_id: str = Depends(get_current_user_id)):
    return {"workers": [], "status": "no workers connected"}


@router.get("/system/failed-jobs")
def failed_jobs(user_id: str = Depends(get_current_user_id)):
    return {"failed_jobs": []}
