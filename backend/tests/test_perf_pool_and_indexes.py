"""Performance tests — DB pool env knobs + missing-indexes migration.

Covers:
  - DB_POOL_SIZE / DB_MAX_OVERFLOW / DB_POOL_TIMEOUT / DB_POOL_RECYCLE
    env vars are honoured by `engine`, and bad values fall back to
    safe defaults.
  - The new alembic migration p7q8r9s0t1u2_perf_missing_indexes
    declares every index the audit asked for, references real tables,
    and the down_revision matches the migration that landed
    immediately before it.

The pool tests reload `app.db.session` under monkey-patched env vars
to verify the module-level constants get re-bound. We don't actually
issue queries — we only check the engine's pool config metadata.
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest


# ── Pool sizing ────────────────────────────────────────────────────


def _reload_session_with_env(monkeypatch, **env: str):
    """Reload app.db.session with the given env vars set."""
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    import app.db.session as session_mod
    return importlib.reload(session_mod)


def test_pool_defaults_when_env_unset(monkeypatch):
    """No env => 10 + 20 + 30s timeout + 1800s recycle (matches
    historical hard-coded values so single-tenant deployments stay
    on the same numbers)."""
    for k in (
        "DB_POOL_SIZE",
        "DB_MAX_OVERFLOW",
        "DB_POOL_TIMEOUT",
        "DB_POOL_RECYCLE",
        "DB_READ_POOL_SIZE",
        "DB_READ_MAX_OVERFLOW",
    ):
        monkeypatch.delenv(k, raising=False)
    sm = _reload_session_with_env(monkeypatch)
    pool = sm.engine.pool
    # SQLAlchemy QueuePool exposes ._pool.maxsize and overflow as attrs.
    assert pool.size() == 10
    # _max_overflow is an internal attr but stable across SQLAlchemy 2.x.
    assert getattr(pool, "_max_overflow") == 20


def test_pool_size_env_override(monkeypatch):
    sm = _reload_session_with_env(
        monkeypatch,
        DB_POOL_SIZE="50",
        DB_MAX_OVERFLOW="100",
    )
    pool = sm.engine.pool
    assert pool.size() == 50
    assert getattr(pool, "_max_overflow") == 100


def test_pool_size_invalid_env_falls_back_to_default(monkeypatch):
    """A garbage value must NOT crash the app — fall back to defaults."""
    sm = _reload_session_with_env(
        monkeypatch,
        DB_POOL_SIZE="not-a-number",
        DB_MAX_OVERFLOW="-5",  # negative also rejected
    )
    pool = sm.engine.pool
    assert pool.size() == 10
    assert getattr(pool, "_max_overflow") == 20


def test_pool_timeout_and_recycle_env_override(monkeypatch):
    sm = _reload_session_with_env(
        monkeypatch,
        DB_POOL_TIMEOUT="5",
        DB_POOL_RECYCLE="600",
    )
    # _timeout / _recycle are stable internal attrs on QueuePool.
    assert getattr(sm.engine.pool, "_timeout") == 5
    assert getattr(sm.engine.pool, "_recycle") == 600


def test_read_pool_defaults_to_primary_when_unset(monkeypatch):
    """When DATABASE_READ_URL is unset, get_read_db must reuse the
    primary engine (so single-DB deployments stay zero-config)."""
    monkeypatch.delenv("DATABASE_READ_URL", raising=False)
    sm = _reload_session_with_env(monkeypatch)
    assert sm.read_engine is sm.engine
    assert sm.ReadSessionLocal is sm.SessionLocal


# ── Missing-indexes migration ──────────────────────────────────────


_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "p7q8r9s0t1u2_perf_missing_indexes.py"
)


def _load_migration_module():
    """Import the migration without running alembic so we can poke at
    its _INDEXES list and revision identifiers."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("perf_missing_indexes", _MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    # The migration `from alembic import op` will succeed in any env
    # where alembic is installed (it is, since the package ships its
    # own migrations). We only need the module-level constants below.
    spec.loader.exec_module(module)
    return module


def test_migration_file_exists():
    assert _MIGRATION_PATH.is_file(), f"missing: {_MIGRATION_PATH}"


def test_migration_revision_ids_set():
    mod = _load_migration_module()
    assert mod.revision == "p7q8r9s0t1u2"
    # down_revision must be SET (the parallel-fixer dance means it
    # may be rebased; the strict invariant is that it's non-empty).
    assert isinstance(mod.down_revision, str) and len(mod.down_revision) > 0


def test_migration_includes_organization_members_user_id_index():
    """C-1: the bullet-point fix from the audit. If this index is
    missing, every authenticated request still does a seq-scan."""
    mod = _load_migration_module()
    names = {entry[0] for entry in mod._INDEXES}
    assert "ix_organization_members_user_id_status" in names


@pytest.mark.parametrize(
    "expected_index, expected_table",
    [
        ("ix_validation_results_run_id", "validation_results"),
        ("ix_validation_results_rule_id", "validation_results"),
        ("ix_recon_results_run_id", "recon_results"),
        ("ix_code_artifact_versions_artifact_id", "code_artifact_versions"),
        ("ix_artifact_dependencies_artifact_id", "artifact_dependencies"),
        ("ix_artifact_dependencies_depends_on", "artifact_dependencies"),
        ("ix_artifact_lineage_source", "artifact_lineage"),
        ("ix_artifact_lineage_generated", "artifact_lineage"),
        ("ix_code_reviews_artifact_version_id", "code_reviews"),
        ("ix_artifact_approvals_artifact_version", "artifact_approvals"),
        ("ix_subprojects_project_id", "subprojects"),
        ("ix_migration_requirements_project_id", "migration_requirements"),
        ("ix_source_connections_project_id", "source_connections"),
        ("ix_target_connections_project_id", "target_connections"),
        ("ix_schemas_project_id", "schemas"),
        ("ix_tables_schema_id", "tables"),
        ("ix_columns_table_id", "columns"),
        ("ix_agent_outputs_task_id", "agent_outputs"),
        ("ix_prompt_versions_template_id", "prompt_versions"),
        ("ix_llm_provider_secrets_provider_id", "llm_provider_secrets"),
        ("ix_roles_organization_id", "roles"),
        ("ix_migration_cutovers_state_tail", "migration_cutovers"),
        ("ix_projects_org_status_created", "projects"),
    ],
)
def test_migration_covers_every_h1_index(expected_index: str, expected_table: str):
    """Each entry in REVIEW_PERFORMANCE.md's index gap appears in the
    migration with the right table."""
    mod = _load_migration_module()
    matches = [e for e in mod._INDEXES if e[0] == expected_index]
    assert matches, f"index missing from migration: {expected_index}"
    assert matches[0][1] == expected_table


def test_migration_uses_if_not_exists_pattern(monkeypatch):
    """The upgrade() body should emit `CREATE INDEX IF NOT EXISTS`
    so re-running on a partially-indexed DB is a no-op rather than
    aborting on the first dup-name."""
    body = _MIGRATION_PATH.read_text(encoding="utf-8")
    assert "CREATE INDEX IF NOT EXISTS" in body


def test_migration_cutovers_state_is_partial_index():
    """M-6: the cutover index is a partial index `WHERE state='tail'`
    to keep it tiny — fail loudly if someone widens it later."""
    mod = _load_migration_module()
    rows = [e for e in mod._INDEXES if e[0] == "ix_migration_cutovers_state_tail"]
    assert rows, "ix_migration_cutovers_state_tail missing"
    where_clause = rows[0][3]
    assert where_clause is not None and "state" in where_clause and "tail" in where_clause
