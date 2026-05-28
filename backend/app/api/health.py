from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str


class ReadyResponse(BaseModel):
    status: str
    # SC-018: `database` / `detail` are kept in the schema for backward
    # compatibility (clients may still read them) but are no longer
    # populated — the response body is now identical regardless of DB
    # state so an attacker can't use /readyz to detect when the DB is
    # down and time an exploit. The HTTP status code (200 vs 503) is the
    # only differentiator, which is all k8s/LB probes need.
    database: str | None = None
    detail: str | None = None


# Single source of truth for the API version. Same constant feeds FastAPI's
# `app.version` so /health no longer drifts from /openapi.json.
APP_VERSION = "0.1.0"


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Liveness probe — minimal, never reaches out to dependencies.

    Use for container/k8s liveness so a transient DB blip does not restart
    the pod. For readiness use /readyz.
    """
    return HealthResponse(
        status="healthy",
        app=settings.APP_NAME,
        version=APP_VERSION,
    )


@router.get("/readyz", response_model=ReadyResponse)
async def readiness_check(response: Response, db: Session = Depends(get_db)):
    """Readiness probe — DB must be reachable before we accept traffic.

    Returns 503 with a status payload if Postgres is unreachable so the load
    balancer / k8s service can route around a degraded replica during boot or
    failover. Redis + Temporal are not gated on because the API can serve
    most reads without them; those are observability inputs only.

    REVIEW_API_CONTRACT health.py MED: previously the 503 body echoed the
    raw exception text, leaking DB host/port to anyone hitting /readyz.
    The detail is now a generic string; operators read the real cause
    from server logs.
    """
    try:
        db.execute(text("SELECT 1"))
        # SC-018: uniform body — no `database`/`detail` field that would
        # leak internal state. Status code 200 signals ready.
        return ReadyResponse(status="ok")
    except Exception as exc:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).exception("Readiness probe DB check failed: %s", exc)
        response.status_code = 503
        # SC-018: identical shape to the 200 body — only the HTTP status
        # code differs. The real cause is in the server logs above.
        return ReadyResponse(status="not_ready")
