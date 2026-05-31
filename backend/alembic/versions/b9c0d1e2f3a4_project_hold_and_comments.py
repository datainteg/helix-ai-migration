"""Add projects.on_hold + project_comments

Operational hold flag on projects (blocks new workflow starts) and a project
comment/activity timeline that also records hold/live toggle reasons.

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-05-31
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "b9c0d1e2f3a4"
down_revision = "a8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("on_hold", sa.Boolean(), nullable=False, server_default="false"))
    op.create_table(
        "project_comments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", sa.String(length=36), nullable=True),
        sa.Column("author_name", sa.String(length=255), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="comment"),
        sa.Column("body", sa.Text(), nullable=False),
    )
    op.create_index("ix_project_comments_project_id", "project_comments", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_project_comments_project_id", table_name="project_comments")
    op.drop_table("project_comments")
    op.drop_column("projects", "on_hold")
