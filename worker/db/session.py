"""Worker-local DB session.

The worker no longer borrows backend's `app.db.session.SessionLocal`
(GAP 8). Both processes still talk to the same Postgres — they just
maintain independent SQLAlchemy engines so the worker doesn't drag in
backend's settings module, Sentry init, OTLP wiring, FastAPI middleware,
etc. when a Temporal activity boots.

Connection details come from `DATABASE_URL` directly (psycopg2 scheme).
Pool size kept small (3 + 2 overflow) because the worker only persists
workflow steps; it's not a hot-path query workload.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://helix:helix@postgres:5432/helix",
)

_engine = create_engine(
    _DATABASE_URL,
    pool_pre_ping=True,
    pool_size=3,
    max_overflow=2,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


@contextmanager
def get_session() -> Iterator[Session]:
    """Yield a worker DB session and guarantee close."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
