"""perf — missing indexes batch (PERF-3 / H-1 / C-1 / M-6)

Adds the indexes flagged by REVIEW_PERFORMANCE.md (FK columns, hot filter
columns) in one batch so operators apply them with a single `alembic
upgrade head`.

Coverage:
- C-1   organization_members(user_id, status)   ← every authenticated request
- H-1   FK indexes on validation_results, recon_results, code_artifact_versions,
        artifact_dependencies, artifact_lineage, code_reviews, artifact_approvals,
        subprojects, migration_requirements, source_connections, target_connections,
        schemas, tables, columns, agent_outputs, prompt_versions,
        llm_provider_secrets, roles
- M-6   migration_cutovers(state)  (partial WHERE state='tail' for CDC poll)
- C-4   ix_projects_org_status_created  (covers `WHERE org_id AND status … ORDER BY created_at`)

Skipped (already present elsewhere):
- password_reset_tokens(user_id)        → c4d5e6f7a8b9
- webhook_deliveries(endpoint_id)       → f7a8b9c0d1e2

Index creation uses `IF NOT EXISTS` via raw SQL so re-running the migration
on an already-partially-indexed DB does not abort. Plain (non-CONCURRENT)
indexes — alembic wraps each migration in a transaction and CREATE INDEX
CONCURRENTLY is not transaction-safe. Operators running into lock pressure
should drop+rebuild concurrently outside alembic.

Revision ID: p7q8r9s0t1u2
Revises: 8f881cfc333e
Create Date: 2026-05-26
"""

from alembic import op


revision = "p7q8r9s0t1u2"
down_revision = "8f881cfc333e"


# (index_name, table, columns_sql, optional WHERE clause)
_INDEXES: list[tuple[str, str, str, str | None]] = [
    # ── C-1: organization_members hot path on every authenticated request
    ("ix_organization_members_user_id_status", "organization_members", "(user_id, status)", None),
    ("ix_organization_members_org_id",         "organization_members", "(organization_id)", None),

    # ── H-1: FK indexes
    ("ix_validation_results_run_id",           "validation_results",     "(run_id)",  None),
    ("ix_validation_results_rule_id",          "validation_results",     "(rule_id)", None),
    ("ix_recon_results_run_id",                "recon_results",          "(run_id)",  None),
    ("ix_code_artifact_versions_artifact_id",  "code_artifact_versions", "(artifact_id)", None),
    ("ix_artifact_dependencies_artifact_id",   "artifact_dependencies",  "(artifact_id)", None),
    ("ix_artifact_dependencies_depends_on",    "artifact_dependencies",  "(depends_on_artifact_id)", None),
    ("ix_artifact_lineage_source",             "artifact_lineage",       "(source_artifact_id)", None),
    ("ix_artifact_lineage_generated",          "artifact_lineage",       "(generated_artifact_id)", None),
    ("ix_code_reviews_artifact_version_id",    "code_reviews",           "(artifact_version_id)", None),
    ("ix_artifact_approvals_artifact_version", "artifact_approvals",     "(artifact_version_id)", None),
    ("ix_subprojects_project_id",              "subprojects",            "(project_id)", None),
    ("ix_migration_requirements_project_id",   "migration_requirements", "(project_id)", None),
    ("ix_source_connections_project_id",       "source_connections",     "(project_id)", None),
    ("ix_target_connections_project_id",       "target_connections",     "(project_id)", None),
    ("ix_schemas_project_id",                  "schemas",                "(project_id)", None),
    ("ix_tables_schema_id",                    "tables",                 "(schema_id)", None),
    ("ix_columns_table_id",                    "columns",                "(table_id)", None),
    ("ix_agent_outputs_task_id",               "agent_outputs",          "(task_id)", None),
    ("ix_prompt_versions_template_id",         "prompt_versions",        "(template_id)", None),
    ("ix_llm_provider_secrets_provider_id",    "llm_provider_secrets",   "(provider_id)", None),
    ("ix_roles_organization_id",               "roles",                  "(organization_id)", None),

    # ── M-6: CDC tail-state poll. Partial index keeps the index tiny.
    ("ix_migration_cutovers_state_tail",       "migration_cutovers",     "(state)", "state = 'tail'"),

    # ── C-4: list_projects ORDER BY created_at DESC WHERE org_id, status
    ("ix_projects_org_status_created",         "projects",               "(organization_id, status, created_at DESC)", None),
]


def upgrade() -> None:
    for name, table, cols, where in _INDEXES:
        where_clause = f" WHERE {where}" if where else ""
        op.execute(
            f'CREATE INDEX IF NOT EXISTS "{name}" '
            f'ON "{table}" {cols}{where_clause}'
        )


def downgrade() -> None:
    for name, table, _cols, _where in reversed(_INDEXES):
        op.execute(f'DROP INDEX IF EXISTS "{name}"')
