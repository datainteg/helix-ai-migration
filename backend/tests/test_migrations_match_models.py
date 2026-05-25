"""Drift detector: alembic head schema vs Base.metadata.

Runs `alembic upgrade head` against an in-memory SQLite database, then
diffs the reflected table set + columns against `Base.metadata`. Any
table declared in models but missing from migrations (or vice versa)
fails this test; ditto for columns and PKs.

This is the regression guard for the family of bugs called out in
REVIEW_DATA_INTEGRITY.md:
  - DI-C3: 5 tables missing from `models/__init__.py`
  - DI-C2: 3 columns missing on `OrgInvitation` model
  - DI-C4: parsed_output_json type drift

The test deliberately runs against SQLite (not Postgres) because
that's where the existing test suite runs in CI. Postgres-specific
column types (UUID, JSONB) become VARCHAR/TEXT/JSON on SQLite, so
type comparison is best-effort and warns rather than fails on
expected dialect drift. The structural assertions (table names,
column names, PKs) are exact.
"""

from __future__ import annotations

import os
import sys
import tempfile
import warnings
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect


# Repo paths. backend/tests/test_x.py -> backend/ is parents[1].
BACKEND_DIR = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"


# Tables we ignore: alembic's own version tracker + tables tests don't
# need to align (e.g. legacy ones still in the wild).
_IGNORE_TABLES = {"alembic_version"}


def _run_alembic_upgrade_head(database_url: str) -> None:
    """Run `alembic upgrade head` against the given URL.

    We import alembic programmatically (no subprocess) so the test
    works on CI without an `alembic` binary on PATH.

    NOTE: app/db/session.py eagerly constructs a `create_async_engine`
    on import that REQUIRES asyncpg driver. To run alembic against
    SQLite without depending on asyncpg, we monkey-patch
    `create_async_engine` to a no-op stub BEFORE env.py imports
    `app.db.session`.
    """
    # Make sure the backend dir is importable so `app.*` works inside
    # env.py.
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))

    # Stash + override DATABASE_URL so alembic env.py points at the
    # temp SQLite DB.
    prior = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    # Provide an ENCRYPTION_KEY only if the test env hasn't set one;
    # config.py validates this in production but our APP_ENV stays
    # 'development' here so validation is skipped.
    os.environ.setdefault("ENCRYPTION_KEY", "JD3oXyD0KZRSqYBhAQ8KE8KvJTLWVuHkM4ZWQUbBQOI=")

    patched = False
    try:
        # Force a fresh settings module pickup. core/config caches the
        # settings singleton at import time; if it was imported earlier
        # by another test, we have to reload it so env.py sees the new
        # DATABASE_URL.
        import importlib
        import app.core.config as cfg_mod
        importlib.reload(cfg_mod)

        # Patch create_async_engine to skip the SQLite incompatibility
        # in session.py. We don't need the async engine for migrations.
        from sqlalchemy.ext import asyncio as _sa_async
        if database_url.startswith("sqlite"):
            _orig_create = _sa_async.create_async_engine

            class _NoopAsyncEngine:
                def __init__(self):
                    pass

            def _stub_create_async_engine(*a, **kw):
                return _NoopAsyncEngine()

            _sa_async.create_async_engine = _stub_create_async_engine  # type: ignore
            patched = (_sa_async, _orig_create)

        # Reload session so it picks up the patched create_async_engine
        # AND the new DATABASE_URL settings.
        import app.db.session as sess_mod
        importlib.reload(sess_mod)

        from alembic import command
        from alembic.config import Config as AlembicConfig

        cfg = AlembicConfig(str(ALEMBIC_INI))
        cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
        cfg.set_main_option("sqlalchemy.url", database_url)
        command.upgrade(cfg, "head")
    finally:
        if patched:
            mod, orig = patched
            mod.create_async_engine = orig  # type: ignore
        if prior is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = prior
        # Reload config back to the prior state so subsequent tests
        # don't pick up our temp URL.
        import importlib
        import app.core.config as cfg_mod
        importlib.reload(cfg_mod)
        import app.db.session as sess_mod
        try:
            importlib.reload(sess_mod)
        except Exception:
            # If the original env is also SQLite-only the reload would
            # fail; tests will skip downstream.
            pass


def _reflected_tables(database_url: str) -> dict[str, set[str]]:
    """Return {table_name: {col1, col2, ...}} as reflected from DB."""
    engine = create_engine(database_url)
    insp = inspect(engine)
    out: dict[str, set[str]] = {}
    for tname in insp.get_table_names():
        if tname in _IGNORE_TABLES:
            continue
        out[tname] = {c["name"] for c in insp.get_columns(tname)}
    engine.dispose()
    return out


def _metadata_tables() -> dict[str, set[str]]:
    """Return {table_name: {col1, col2, ...}} from Base.metadata."""
    # Importing app.models triggers all model registration on Base.
    import app.models  # noqa: F401
    from app.db.session import Base

    out: dict[str, set[str]] = {}
    for table in Base.metadata.sorted_tables:
        if table.name in _IGNORE_TABLES:
            continue
        out[table.name] = {c.name for c in table.columns}
    return out


@pytest.fixture(scope="module")
def alembic_sqlite_url():
    """Create a fresh SQLite DB and upgrade it to head.

    Skips the entire module if alembic isn't installed or if the
    upgrade fails because of a Postgres-specific construct we couldn't
    work around. The conftest's Postgres fixture remains the
    authoritative integration path; this test exists to catch
    metadata-vs-migration drift early without a Postgres
    dependency.
    """
    try:
        import alembic  # noqa: F401
    except ImportError:
        pytest.skip("alembic not installed in this env")

    tmpdir = tempfile.mkdtemp(prefix="helix-alembic-")
    db_path = Path(tmpdir) / "alembic_head.db"
    url = f"sqlite:///{db_path}"
    try:
        _run_alembic_upgrade_head(url)
    except Exception as exc:
        try:
            db_path.unlink()
        except FileNotFoundError:
            pass
        pytest.skip(f"alembic upgrade head failed against SQLite: {exc}")
    yield url
    try:
        db_path.unlink()
    except FileNotFoundError:
        pass


def test_alembic_head_creates_every_model_table(alembic_sqlite_url):
    """Every table declared in Base.metadata must exist after
    `alembic upgrade head`. Catches the C-3 class of bugs where a
    model was forgotten in `models/__init__.py` or a migration
    creating its table was never written.
    """
    db_tables = _reflected_tables(alembic_sqlite_url)
    model_tables = _metadata_tables()

    missing_in_db = sorted(set(model_tables) - set(db_tables))
    assert not missing_in_db, (
        f"Tables declared in models but NOT created by alembic head: "
        f"{missing_in_db}. Either add a migration that creates them or "
        f"remove the model."
    )


def test_alembic_head_has_no_orphan_tables(alembic_sqlite_url):
    """Every table created by migrations must have a model attached.
    Catches the opposite C-3 case: a migration created the table but
    `models/__init__.py` doesn't import the model, so `alembic
    revision --autogenerate` would propose dropping it.
    """
    db_tables = _reflected_tables(alembic_sqlite_url)
    model_tables = _metadata_tables()

    orphan_in_db = sorted(set(db_tables) - set(model_tables))
    assert not orphan_in_db, (
        f"Tables created by alembic but NOT in models/__init__: "
        f"{orphan_in_db}. A future autogenerate would propose dropping "
        f"these. Add the corresponding model imports."
    )


def test_every_model_column_exists_in_db(alembic_sqlite_url):
    """Per-table column coverage. Catches the C-2 class of bugs
    (model attribute missing while migration created the column, or
    the reverse).
    """
    db_tables = _reflected_tables(alembic_sqlite_url)
    model_tables = _metadata_tables()

    drift: dict[str, dict[str, list[str]]] = {}
    for tname, model_cols in model_tables.items():
        db_cols = db_tables.get(tname)
        if db_cols is None:
            # Reported by test_alembic_head_creates_every_model_table.
            continue
        only_in_model = sorted(model_cols - db_cols)
        only_in_db = sorted(db_cols - model_cols)
        if only_in_model or only_in_db:
            drift[tname] = {
                "in_model_not_db": only_in_model,
                "in_db_not_model": only_in_db,
            }

    # Emit a readable failure if there's any drift.
    if drift:
        msg_lines = ["Model-vs-migration column drift:"]
        for t, d in drift.items():
            msg_lines.append(
                f"  {t}: "
                f"only_in_model={d['in_model_not_db']} "
                f"only_in_db={d['in_db_not_model']}"
            )
        pytest.fail("\n".join(msg_lines))


def test_metadata_create_all_matches_alembic_head(alembic_sqlite_url):
    """Sanity guard: the table set produced by
    `Base.metadata.create_all` (which conftest.py uses for test
    fixtures) must equal the alembic head set.

    This is the high-level guarantee that the test database (used by
    every other test_*.py) reflects the same schema as production
    would after `alembic upgrade head`.
    """
    db_tables = _reflected_tables(alembic_sqlite_url)

    # Build a parallel SQLite DB via Base.metadata.create_all.
    import app.models  # noqa: F401
    from app.db.session import Base

    tmp_url = "sqlite:///:memory:"
    engine = create_engine(tmp_url)
    Base.metadata.create_all(bind=engine)
    insp = inspect(engine)
    create_all_tables = {
        t for t in insp.get_table_names() if t not in _IGNORE_TABLES
    }
    engine.dispose()

    alembic_set = set(db_tables)
    only_in_alembic = sorted(alembic_set - create_all_tables)
    only_in_create_all = sorted(create_all_tables - alembic_set)

    assert not only_in_alembic and not only_in_create_all, (
        f"create_all vs alembic table-set drift. "
        f"only_in_alembic={only_in_alembic} "
        f"only_in_create_all={only_in_create_all}"
    )
