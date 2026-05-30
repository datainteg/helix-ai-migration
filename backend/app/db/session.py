import os

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


# ── Pool sizing (env-configurable, closes REVIEW_PERFORMANCE.md verdict) ──
# Defaults kept at 10/20 so existing single-tenant deployments keep their
# current behaviour. Operators can raise these in line with the
# documented activity-concurrency for their workload — the audit calls
# 10+20 the "single most likely cause of a 'Postgres is fine but the
# app is wedged' outage" at scale.
#
# Pool-timeout is also env-configurable so a checkout starvation surfaces
# as a 503 rather than hanging the request indefinitely.
def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        val = int(raw)
    except ValueError:
        return default
    return val if val >= 0 else default


_POOL_SIZE = _int_env("DB_POOL_SIZE", 10)
_MAX_OVERFLOW = _int_env("DB_MAX_OVERFLOW", 20)
_POOL_TIMEOUT = _int_env("DB_POOL_TIMEOUT", 30)
_POOL_RECYCLE = _int_env("DB_POOL_RECYCLE", 1800)  # 30 min; mitigates idle-tcp drops

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=_POOL_SIZE,
    max_overflow=_MAX_OVERFLOW,
    pool_timeout=_POOL_TIMEOUT,
    pool_recycle=_POOL_RECYCLE,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ── Optional read-replica routing ──────────────────────────────────────
# Set DATABASE_READ_URL in .env to point hot-path read endpoints (project
# list, audit-log pagination, dashboard rollups) at a replica. Falls back to
# the primary when unset so single-DB deployments stay zero-config.
#
# Replica pool size defaults to the primary pool size but can be overridden
# independently via DB_READ_POOL_SIZE / DB_READ_MAX_OVERFLOW for workloads
# where the replica handles a much larger read volume than the primary.
_replica_url = os.getenv("DATABASE_READ_URL", "").strip()
if _replica_url:
    read_engine = create_engine(
        _replica_url,
        pool_pre_ping=True,
        pool_size=_int_env("DB_READ_POOL_SIZE", _POOL_SIZE),
        max_overflow=_int_env("DB_READ_MAX_OVERFLOW", _MAX_OVERFLOW),
        pool_timeout=_POOL_TIMEOUT,
        pool_recycle=_POOL_RECYCLE,
    )
    ReadSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=read_engine)
else:
    read_engine = engine
    ReadSessionLocal = SessionLocal

# Async engine — uses the asyncpg driver. Built LAZILY so that merely importing
# this module does NOT require asyncpg to be installed. The Temporal worker
# imports app.models (which imports this module) for the shared ORM classes but
# runs purely sync (psycopg2); creating the asyncpg engine at import time made
# `from app.models... import ...` raise ModuleNotFoundError: asyncpg in the
# worker. The engine is now created on first async request instead.
_async_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
_async_engine = None
_AsyncSessionLocal = None


def _get_async_sessionmaker():
    global _async_engine, _AsyncSessionLocal
    if _AsyncSessionLocal is None:
        _async_engine = create_async_engine(
            _async_url,
            pool_pre_ping=True,
            pool_size=_POOL_SIZE,
            max_overflow=_MAX_OVERFLOW,
            pool_timeout=_POOL_TIMEOUT,
            pool_recycle=_POOL_RECYCLE,
        )
        _AsyncSessionLocal = async_sessionmaker(_async_engine, class_=AsyncSession, expire_on_commit=False)
    return _AsyncSessionLocal


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_read_db():
    """FastAPI dependency for read-only endpoints. Routes to the replica
    when DATABASE_READ_URL is configured; otherwise behaves identically to
    get_db. Use only on endpoints that NEVER write — writes on a replica
    fail at the DB layer.

    Endpoints worth migrating (per REVIEW_PERFORMANCE.md verdict —
    "the read-replica feature is effectively unused"): list_projects,
    list_workflow_runs, list_executions, dashboard rollups, audit-log
    pagination. Fixer C owns the actual endpoint switch-overs; this
    module just provides the dependency.
    """
    db = ReadSessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db():
    async with _get_async_sessionmaker()() as session:
        yield session
