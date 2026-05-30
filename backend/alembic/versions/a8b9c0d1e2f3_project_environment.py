"""Add projects.environment

Target deployment environment label (dev/staging/prod/…) collected at project
creation. Nullable so existing rows are unaffected.

Revision ID: a8b9c0d1e2f3
Revises: z7a8b9c0d1e2
Create Date: 2026-05-31
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "a8b9c0d1e2f3"
down_revision = "z7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("environment", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "environment")
