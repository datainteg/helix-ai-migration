"""Add workflow_runs.kind to distinguish BMAD vs DB-migration workflows

The DB-migration agent chain (SchemaAnalyst→TypeMapper→ScriptGenerator→
Reconciler) runs alongside the BMAD pipeline on the same worker/queue and
shares the workflow_runs/workflow_steps tables. `kind` lets readers (and a
kind-aware replay) tell them apart. Defaults to 'bmad' (server_default) so
every existing row and any caller that omits it is unchanged.

Revision ID: w4x5y6z7a8b9
Revises: v3w4x5y6z7a8
Create Date: 2026-05-30
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "w4x5y6z7a8b9"
down_revision = "v3w4x5y6z7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workflow_runs",
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="bmad"),
    )


def downgrade() -> None:
    op.drop_column("workflow_runs", "kind")
