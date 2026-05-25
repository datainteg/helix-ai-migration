import os

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ── Optional read-replica routing ──────────────────────────────────────
# Set DATABASE_READ_URL in .env to point hot-path read endpoints (project
# list, audit-log pagination, dashboard rollups) at a replica. Falls back to
# the primary when unset so single-DB deployments stay zero-config.
_replica_url = os.getenv("DATABASE_READ_URL", "").strip()
if _replica_url:
    read_engine = create_engine(_replica_url, pool_pre_ping=True, pool_size=10, max_overflow=20)
    ReadSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=read_engine)
else:
    read_engine = engine
    ReadSessionLocal = SessionLocal

# Async engine — uses asyncpg driver. DATABASE_URL uses psycopg2 scheme;
# swap to asyncpg for the async engine only.
_async_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
async_engine = create_async_engine(_async_url, pool_pre_ping=True, pool_size=10, max_overflow=20)
AsyncSessionLocal = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)


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
    fail at the DB layer."""
    db = ReadSessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db():
    async with AsyncSessionLocal() as session:
        yield session
