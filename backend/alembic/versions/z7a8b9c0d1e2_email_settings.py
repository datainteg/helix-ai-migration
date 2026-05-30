"""Add email_settings (per-org SMTP / SendGrid config)

Admin-editable, DB-backed mail transport so SMTP can be set up + tested from the
UI without editing .env. Password + API key columns hold encrypted values.

Revision ID: z7a8b9c0d1e2
Revises: y6z7a8b9c0d1
Create Date: 2026-05-30
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "z7a8b9c0d1e2"
down_revision = "y6z7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_settings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("provider", sa.String(length=20), nullable=False, server_default="smtp"),
        sa.Column("from_email", sa.String(length=255), nullable=True),
        sa.Column("from_name", sa.String(length=255), nullable=True),
        sa.Column("smtp_host", sa.String(length=255), nullable=True),
        sa.Column("smtp_port", sa.Integer(), nullable=False, server_default="587"),
        sa.Column("smtp_user", sa.String(length=255), nullable=True),
        sa.Column("smtp_password_enc", sa.String(length=1000), nullable=True),
        sa.Column("smtp_tls", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sendgrid_api_key_enc", sa.String(length=1000), nullable=True),
        sa.UniqueConstraint("organization_id", name="uq_email_settings_org"),
    )
    op.create_index("ix_email_settings_organization_id", "email_settings", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_email_settings_organization_id", table_name="email_settings")
    op.drop_table("email_settings")
