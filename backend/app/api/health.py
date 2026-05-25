from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Liveness probe — minimal, never reaches out to dependencies.

    Use for container/k8s liveness so a transient DB blip does not restart
    the pod. For readiness use /readyz.
    """
    return {
        "status": "healthy",
        "app": "Helix Migration",
        "version": "0.1.0",
    }


@router.get("/readyz")
async def readiness_check(response: Response, db: Session = Depends(get_db)):
    """Readiness probe — DB must be reachable before we accept traffic.

    Returns 503 with a status payload if Postgres is unreachable so the load
    balancer / k8s service can route around a degraded replica during boot or
    failover. Redis + Temporal are not gated on because the API can serve
    most reads without them; those are observability inputs only.
    """
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}
    except Exception as exc:  # noqa: BLE001
        response.status_code = 503
        return {"status": "not_ready", "database": "down", "detail": str(exc)[:200]}
