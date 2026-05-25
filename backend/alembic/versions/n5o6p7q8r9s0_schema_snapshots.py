"""source_schema_snapshots

Drift detection table — captures the source schema at a point in time so
subsequent snapshots can be compared against the baseline.

Revision ID: n5o6p7q8r9s0
Revises: m4n5o6p7q8r9
Create Date: 2026-05-25
"""

from alembic import op
import sqlalchemy as sa


revision = "n5o6p7q8r9s0"
down_revision = "m4n5o6p7q8r9"


def upgrade():
    op.create_table(
        "source_schema_snapshots",
        sa.Column("id",               sa.String(36), primary_key=True),
        sa.Column("created_at",       sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at",       sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("organization_id",  sa.String(36), nullable=False, index=True),
        sa.Column("project_id",       sa.String(36), nullable=False, index=True),
        sa.Column("source_ref",       sa.String(255), nullable=False, index=True),
        sa.Column("payload",          sa.Text, nullable=False),
        sa.Column("table_count",      sa.Integer, server_default="0", nullable=False),
        sa.Column("column_count",     sa.Integer, server_default="0", nullable=False),
        sa.Column("taken_at",         sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes",            sa.Text, nullable=True),
    )
    op.create_index(
        "ix_schema_snapshots_project_source_taken",
        "source_schema_snapshots",
        ["project_id", "source_ref", "taken_at"],
    )


def downgrade():
    op.drop_index("ix_schema_snapshots_project_source_taken", table_name="source_schema_snapshots")
    op.drop_table("source_schema_snapshots")
