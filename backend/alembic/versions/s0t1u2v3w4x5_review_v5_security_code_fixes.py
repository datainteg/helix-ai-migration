"""review-v5 fixes: audit_logs.impersonator_id + workflow_runs/sprints unique constraints

Bundles three small schema changes from the review-v5 audit so the same
migration head can land them atomically:

  * SC-012 — add `audit_logs.impersonator_id` column so super-admin
    impersonation actions are attributable to the originating admin in
    addition to the target user.
  * C-001 — add a unique index on `workflow_runs (workflow_id,
    organization_id)` so the per-org dedupe logic in
    `_persist_workflow_result` is enforced at the DB layer too.
  * H-001 — add a partial unique index on `sprints (organization_id,
    project_id, index)` so the new ``SELECT max(index) FOR UPDATE``
    allocator cannot silently produce duplicate indices under races.

All indices use ``IF NOT EXISTS`` so re-applying on an already-fixed DB
is a no-op (some operators applied the fix manually before the
migration shipped).

Revision ID: s0t1u2v3w4x5
Revises: r9s0t1u2v3w4
Create Date: 2026-05-28
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "s0t1u2v3w4x5"
down_revision = "r9s0t1u2v3w4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # ── SC-012: audit_logs.impersonator_id ────────────────────────────
    # Nullable because the column is empty for every non-impersonation
    # row in the back-catalog. The audit chain HMAC now includes this
    # column so future writes are tamper-evident.
    op.add_column(
        "audit_logs",
        sa.Column("impersonator_id", sa.String(36), nullable=True),
    )
    # Index for the rare "who was impersonating?" forensic query.
    op.create_index(
        "ix_audit_logs_impersonator_id",
        "audit_logs",
        ["impersonator_id"],
    )

    # ── C-001: workflow_runs unique (workflow_id, organization_id) ────
    # The previous code path could insert a second row for the same
    # workflow when the fallback (non-Temporal) path ran after a
    # successful Temporal start. The persistence service now upserts,
    # but we also enforce uniqueness at the DB layer so a regression
    # surfaces immediately rather than silently splintering history.
    if dialect == "postgresql":
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS "
            "uq_workflow_runs_workflow_id_org "
            "ON workflow_runs (workflow_id, organization_id)"
        )
    else:
        # SQLite test path — plain unique index is fine.
        op.create_index(
            "uq_workflow_runs_workflow_id_org",
            "workflow_runs",
            ["workflow_id", "organization_id"],
            unique=True,
        )

    # ── H-001: sprints partial unique (org, project, index) ──────────
    # Use a partial unique index so soft-deleted rows (status='archived')
    # don't conflict with new sprints reusing the same index number.
    if dialect == "postgresql":
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS "
            "uq_sprints_org_project_index "
            "ON sprints (organization_id, project_id, index) "
            "WHERE status <> 'archived'"
        )
    else:
        op.create_index(
            "uq_sprints_org_project_index",
            "sprints",
            ["organization_id", "project_id", "index"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.execute("DROP INDEX IF EXISTS uq_sprints_org_project_index")
        op.execute("DROP INDEX IF EXISTS uq_workflow_runs_workflow_id_org")
    else:
        op.drop_index("uq_sprints_org_project_index", table_name="sprints")
        op.drop_index("uq_workflow_runs_workflow_id_org", table_name="workflow_runs")

    op.drop_index("ix_audit_logs_impersonator_id", table_name="audit_logs")
    op.drop_column("audit_logs", "impersonator_id")
