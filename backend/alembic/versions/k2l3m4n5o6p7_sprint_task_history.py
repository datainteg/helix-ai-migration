"""sprint_task_history

Append-only log of task status transitions so burndown can be reconstructed
from real data instead of straight-line interpolation. One row per status
change; the API server inserts on `update_task_status`.

Revision ID: k2l3m4n5o6p7
Revises: j1k2l3m4n5o6
Create Date: 2026-05-25
"""

from alembic import op
import sqlalchemy as sa


revision = "k2l3m4n5o6p7"
down_revision = "j1k2l3m4n5o6"


def upgrade():
    op.create_table(
        "sprint_task_history",
        sa.Column("id",              sa.String(36), primary_key=True),
        sa.Column("created_at",      sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at",      sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False, index=True),
        sa.Column("sprint_id",       sa.String(36), sa.ForeignKey("sprints.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("task_id",         sa.String(36), sa.ForeignKey("sprint_tasks.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("from_status",     sa.String(40), nullable=True),
        sa.Column("to_status",       sa.String(40), nullable=False),
        sa.Column("story_points",    sa.Integer, nullable=False, server_default="0"),
        sa.Column("changed_by",      sa.String(36), nullable=True),
    )
    op.create_index(
        "ix_sprint_task_history_sprint_ts",
        "sprint_task_history",
        ["sprint_id", "created_at"],
    )


def downgrade():
    op.drop_index("ix_sprint_task_history_sprint_ts", table_name="sprint_task_history")
    op.drop_table("sprint_task_history")
