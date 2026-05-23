import os

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.dependencies import require_admin
from app.core.config import settings

router = APIRouter(tags=["system"])


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


@router.get("/system/health")
def system_health(user_id: str = Depends(require_admin), db: Session = Depends(get_db)):
    checks = []

    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        checks.append({"component": "database", "status": "healthy"})
    except Exception:
        checks.append({"component": "database", "status": "down"})

    checks.append({"component": "redis", "status": _check_redis()})
    checks.append({"component": "temporal", "status": _check_temporal()})
    checks.append({"component": "worker", "status": "unknown"})

    storage_ok = os.path.exists(settings.ARTIFACT_STORAGE_PATH) if settings.ARTIFACT_STORAGE_PATH else False
    checks.append({"component": "artifact_storage", "status": "healthy" if storage_ok else "unknown"})

    overall = "ok" if all(c["status"] != "down" for c in checks) else "degraded"
    return {"status": overall, "components": checks}


@router.get("/system/workers")
def worker_status(user_id: str = Depends(require_admin)):
    return {"workers": [], "status": "no workers connected"}


@router.get("/system/failed-jobs")
def failed_jobs(user_id: str = Depends(require_admin)):
    return {"failed_jobs": []}
