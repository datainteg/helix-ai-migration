"""proper column types and migration_type field

Revision ID: a1b2c3d4e5f6
Revises: f6a7b8c9d0e1
Create Date: 2026-05-23

Converts String columns to proper types (H-6) and adds migration_type to projects (H-16).
"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "f6a7b8c9d0e1"


def upgrade():
    # H-16: Add migration_type to projects
    op.add_column("projects", sa.Column("migration_type", sa.String(50), nullable=True))

    # H-6: workflow_steps — step_order String → Integer
    op.alter_column("workflow_steps", "step_order",
        existing_type=sa.String(10),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="step_order::integer",
    )

    # H-6: workflow_steps — started_at / completed_at String → DateTime
    op.alter_column("workflow_steps", "started_at",
        existing_type=sa.String(50),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        postgresql_using="started_at::timestamptz",
    )
    op.alter_column("workflow_steps", "completed_at",
        existing_type=sa.String(50),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        postgresql_using="completed_at::timestamptz",
    )

    # H-6: validation_runs — started_at / finished_at String → DateTime
    op.alter_column("validation_runs", "started_at",
        existing_type=sa.String(50),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        postgresql_using="started_at::timestamptz",
    )
    op.alter_column("validation_runs", "finished_at",
        existing_type=sa.String(50),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        postgresql_using="finished_at::timestamptz",
    )

    # H-6: recon_results — mismatch_count String → Integer
    op.alter_column("recon_results", "mismatch_count",
        existing_type=sa.String(20),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using="mismatch_count::integer",
    )

    # H-6: tables — row_count String → Integer
    op.alter_column("tables", "row_count",
        existing_type=sa.String(20),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using="row_count::integer",
    )

    # H-6: columns — nullable String → Boolean, ordinal_position String → Integer
    op.execute("ALTER TABLE columns ALTER COLUMN nullable DROP DEFAULT")
    op.alter_column("columns", "nullable",
        existing_type=sa.String(10),
        type_=sa.Boolean(),
        existing_nullable=True,
        postgresql_using="CASE WHEN nullable = 'YES' OR nullable = 'true' THEN true ELSE false END",
    )
    op.execute("ALTER TABLE columns ALTER COLUMN nullable SET DEFAULT false")
    op.alter_column("columns", "ordinal_position",
        existing_type=sa.String(10),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using="ordinal_position::integer",
    )

    # Add error_message to recon_runs (was missing from model)
    op.add_column("recon_runs", sa.Column("error_message", sa.Text, nullable=True))


def downgrade():
    op.drop_column("recon_runs", "error_message")
    op.alter_column("columns", "ordinal_position", existing_type=sa.Integer(), type_=sa.String(10), existing_nullable=True)
    op.alter_column("columns", "nullable", existing_type=sa.Boolean(), type_=sa.String(10), existing_nullable=True)
    op.alter_column("tables", "row_count", existing_type=sa.Integer(), type_=sa.String(20), existing_nullable=True)
    op.alter_column("recon_results", "mismatch_count", existing_type=sa.Integer(), type_=sa.String(20), existing_nullable=True)
    op.alter_column("validation_runs", "finished_at", existing_type=sa.DateTime(timezone=True), type_=sa.String(50), existing_nullable=True)
    op.alter_column("validation_runs", "started_at", existing_type=sa.DateTime(timezone=True), type_=sa.String(50), existing_nullable=True)
    op.alter_column("workflow_steps", "completed_at", existing_type=sa.DateTime(timezone=True), type_=sa.String(50), existing_nullable=True)
    op.alter_column("workflow_steps", "started_at", existing_type=sa.DateTime(timezone=True), type_=sa.String(50), existing_nullable=True)
    op.alter_column("workflow_steps", "step_order", existing_type=sa.Integer(), type_=sa.String(10), existing_nullable=False)
    op.drop_column("projects", "migration_type")
