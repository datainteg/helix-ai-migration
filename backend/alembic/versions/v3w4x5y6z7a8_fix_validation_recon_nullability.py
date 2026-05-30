"""Repair validation/recon/health nullability inverted by e5f6a7b8c9d0

Migration e5f6a7b8c9d0 built default-less columns with `nullable=not c[1]`,
inverting every intended-nullable column to NOT NULL across validation_rules,
validation_runs, validation_results, recon_runs, recon_results and
system_health_checks. The follow-ups a1b2c3d4e5f6 / t1u2v3w4x5y6 never repaired
it, so the deployed schema contradicts the models and these inserts 500/502:
  - recon results (details_ref/summary/mismatch_count never set) -> recon broken
  - validation-run start (started_at/finished_at omitted) -> broken
  - template clone (target_ref omitted) -> all 5 seeded templates broken

This drops NOT NULL on every column the model marks nullable, widens
system_health_checks.message to varchar(500) to match the model, and creates
the missing project_id indexes the models declare (index=True) but no migration
ever created (live Seq Scans on hot compliance/dashboard paths).

Revision ID: v3w4x5y6z7a8
Revises: u2v3w4x5y6z7
Create Date: 2026-05-30
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "v3w4x5y6z7a8"
down_revision = "u2v3w4x5y6z7"
branch_labels = None
depends_on = None

# (table, column, type) — all marked nullable=True in the models.
_NULLABLE = [
    ("validation_rules", "target_ref", sa.String(length=255)),
    ("validation_rules", "definition", sa.Text()),
    ("validation_runs", "started_at", sa.DateTime(timezone=True)),
    ("validation_runs", "finished_at", sa.DateTime(timezone=True)),
    ("validation_results", "observed_value", sa.String(length=255)),
    ("validation_results", "expected_value", sa.String(length=255)),
    ("recon_runs", "source_ref", sa.String(length=255)),
    ("recon_runs", "target_ref", sa.String(length=255)),
    ("recon_results", "summary", sa.Text()),
    ("recon_results", "mismatch_count", sa.BigInteger()),
    ("recon_results", "details_ref", sa.String(length=500)),
    ("system_health_checks", "message", sa.String(length=255)),
]

_INDEXES = [
    ("ix_validation_rules_project_id", "validation_rules"),
    ("ix_validation_runs_project_id", "validation_runs"),
    ("ix_recon_runs_project_id", "recon_runs"),
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # Test backends build tables straight from the (correct) models.
        return
    for table, col, coltype in _NULLABLE:
        op.alter_column(table, col, existing_type=coltype, nullable=True)
    # message: also widen 255 -> 500 to match the model (String(500)).
    op.alter_column(
        "system_health_checks", "message",
        existing_type=sa.String(length=255), type_=sa.String(length=500), existing_nullable=True,
    )
    # Missing project_id indexes (models declare index=True; never created).
    for name, table in _INDEXES:
        op.execute(f'CREATE INDEX IF NOT EXISTS {name} ON {table} (project_id)')


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for name, _table in _INDEXES:
        op.execute(f'DROP INDEX IF EXISTS {name}')
    op.alter_column(
        "system_health_checks", "message",
        existing_type=sa.String(length=500), type_=sa.String(length=255), existing_nullable=True,
    )
    for table, col, coltype in _NULLABLE:
        op.alter_column(table, col, existing_type=coltype, nullable=False)
