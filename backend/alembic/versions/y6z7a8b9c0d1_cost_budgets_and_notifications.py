"""Add cost_budgets + notifications + notification_rules

Per-agent / per-project spend budgets (cost_budgets) and the in-app
notification system (notifications + notification_rules). All tables follow the
BaseModel convention: String(36) uuid PK, created_at/updated_at timestamptz with
server_default now().

Revision ID: y6z7a8b9c0d1
Revises: x5y6z7a8b9c0
Create Date: 2026-05-30
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "y6z7a8b9c0d1"
down_revision = "x5y6z7a8b9c0"
branch_labels = None
depends_on = None


def _base_cols() -> list:
    return [
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    # ---- cost_budgets ---------------------------------------------------
    op.create_table(
        "cost_budgets",
        *_base_cols(),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("scope_key", sa.String(length=100), nullable=False),
        sa.Column("daily_usd_cap", sa.Float(), nullable=False, server_default="0"),
        sa.Column("monthly_usd_cap", sa.Float(), nullable=False, server_default="0"),
        sa.Column("enforcement", sa.String(length=20), nullable=False, server_default="hard"),
        sa.UniqueConstraint("organization_id", "scope", "scope_key", name="uq_cost_budget_org_scope_key"),
    )
    op.create_index("ix_cost_budgets_organization_id", "cost_budgets", ["organization_id"])

    # ---- notifications --------------------------------------------------
    op.create_table(
        "notifications",
        *_base_cols(),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("type", sa.String(length=60), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="info"),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("link", sa.String(length=500), nullable=True),
        sa.Column("dedupe_key", sa.String(length=120), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_notifications_organization_id", "notifications", ["organization_id"])
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_dedupe_key", "notifications", ["dedupe_key"])
    op.create_index("ix_notifications_org_user_read", "notifications", ["organization_id", "user_id", "read_at"])
    op.create_index("ix_notifications_org_created", "notifications", ["organization_id", "created_at"])

    # ---- notification_rules ---------------------------------------------
    op.create_table(
        "notification_rules",
        *_base_cols(),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("channels", sa.String(length=255), nullable=False, server_default="in_app"),
        sa.UniqueConstraint("organization_id", "event_type", name="uq_notif_rule_org_event"),
    )
    op.create_index("ix_notification_rules_organization_id", "notification_rules", ["organization_id"])


def downgrade() -> None:
    op.drop_table("notification_rules")
    op.drop_index("ix_notifications_org_created", table_name="notifications")
    op.drop_index("ix_notifications_org_user_read", table_name="notifications")
    op.drop_index("ix_notifications_dedupe_key", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_index("ix_notifications_organization_id", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_cost_budgets_organization_id", table_name="cost_budgets")
    op.drop_table("cost_budgets")
