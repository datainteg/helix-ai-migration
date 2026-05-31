"""pre-start approval gate: projects.require_run_approval + workflow_run_requests

Adds the per-project toggle (default ON) and a table of run requests that must
be approved by a project manager before the agents start.

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
"""
from alembic import op
import sqlalchemy as sa

revision = "d1e2f3a4b5c6"
down_revision = "c0d1e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("require_run_approval", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_table(
        "workflow_run_requests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("requirement_id", sa.String(length=36), nullable=False),
        sa.Column("requested_by", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("approver_id", sa.String(length=36), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("workflow_id", sa.String(length=100), nullable=True),
    )
    op.create_index("ix_workflow_run_requests_project_id", "workflow_run_requests", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_workflow_run_requests_project_id", table_name="workflow_run_requests")
    op.drop_table("workflow_run_requests")
    op.drop_column("projects", "require_run_approval")
