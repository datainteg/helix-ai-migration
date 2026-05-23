"""workflow persistence tables

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-23

"""
from alembic import op
import sqlalchemy as sa

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"


def upgrade():
    op.create_table("workflow_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False, index=True),
        sa.Column("project_id", sa.String(36), nullable=False, index=True),
        sa.Column("requirement_id", sa.String(36), nullable=False),
        sa.Column("workflow_id", sa.String(255), nullable=False, unique=True),
        sa.Column("run_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("mode", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table("workflow_steps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workflow_run_id", sa.String(36), sa.ForeignKey("workflow_runs.id"), nullable=False),
        sa.Column("agent_name", sa.String(100), nullable=False),
        sa.Column("step_order", sa.String(10), nullable=False),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("raw_output", sa.Text, nullable=True),
        sa.Column("parsed_output_json", sa.Text, nullable=True),
        sa.Column("provider_name", sa.String(100), nullable=True),
        sa.Column("model_name", sa.String(100), nullable=True),
        sa.Column("prompt_version", sa.String(20), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("started_at", sa.String(50), nullable=True),
        sa.Column("completed_at", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("workflow_steps")
    op.drop_table("workflow_runs")
