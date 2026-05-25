"""sprint_management_tables

Creates the eight Sprint Management tables: sprints, sprint_tasks,
sprint_risks, sprint_approvals, migration_releases, sprint_mapping_nodes,
sprint_mapping_edges, sprint_agent_executions.

Every table is org-scoped + project-scoped so the existing cross-tenant
guards apply uniformly.

Revision ID: j1k2l3m4n5o6
Revises: i0j1k2l3m4n5
Create Date: 2026-05-25
"""

from alembic import op
import sqlalchemy as sa


revision = "j1k2l3m4n5o6"
down_revision = "i0j1k2l3m4n5"


def _ts():
    return sa.DateTime(timezone=True)


def upgrade():
    op.create_table(
        "sprints",
        sa.Column("id",              sa.String(36), primary_key=True),
        sa.Column("created_at",      _ts(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at",      _ts(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False, index=True),
        sa.Column("project_id",      sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("index",           sa.Integer, nullable=False),
        sa.Column("name",            sa.String(255), nullable=False),
        sa.Column("goal",            sa.Text, nullable=True),
        sa.Column("status",          sa.String(40), nullable=False, server_default="planning"),
        sa.Column("health",          sa.String(40), nullable=False, server_default="on-track"),
        sa.Column("start_date",      _ts(), nullable=True),
        sa.Column("end_date",        _ts(), nullable=True),
        sa.Column("metrics",         sa.JSON, nullable=True),
        sa.Column("milestones",      sa.JSON, nullable=True),
    )

    op.create_table(
        "sprint_tasks",
        sa.Column("id",                sa.String(36), primary_key=True),
        sa.Column("created_at",        _ts(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at",        _ts(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("organization_id",   sa.String(36), nullable=False, index=True),
        sa.Column("sprint_id",         sa.String(36), sa.ForeignKey("sprints.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title",             sa.String(500), nullable=False),
        sa.Column("type",              sa.String(40), nullable=False),
        sa.Column("status",            sa.String(40), nullable=False, server_default="backlog"),
        sa.Column("priority",          sa.String(4), nullable=False, server_default="P3"),
        sa.Column("owner_id",          sa.String(36), nullable=True),
        sa.Column("owner_name",        sa.String(255), nullable=True),
        sa.Column("owner_kind",        sa.String(20), nullable=False, server_default="human"),
        sa.Column("ai_agent",          sa.String(64), nullable=True),
        sa.Column("epic_id",           sa.String(64), nullable=True),
        sa.Column("risk_level",        sa.String(20), nullable=False, server_default="low"),
        sa.Column("story_points",      sa.Integer, nullable=False, server_default="0"),
        sa.Column("estimated_hours",   sa.Integer, nullable=False, server_default="0"),
        sa.Column("actual_hours",      sa.Integer, nullable=True),
        sa.Column("validation_status", sa.String(20), nullable=True),
        sa.Column("recon_status",      sa.String(20), nullable=True),
        sa.Column("dependency_ids",    sa.JSON, nullable=True),
        sa.Column("artifact_ids",      sa.JSON, nullable=True),
        sa.Column("blocked_reason",    sa.Text, nullable=True),
    )

    op.create_table(
        "sprint_risks",
        sa.Column("id",              sa.String(36), primary_key=True),
        sa.Column("created_at",      _ts(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at",      _ts(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False, index=True),
        sa.Column("sprint_id",       sa.String(36), sa.ForeignKey("sprints.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title",           sa.String(500), nullable=False),
        sa.Column("category",        sa.String(40), nullable=False),
        sa.Column("level",           sa.String(20), nullable=False),
        sa.Column("description",     sa.Text, nullable=True),
        sa.Column("mitigation",      sa.Text, nullable=True),
        sa.Column("status",          sa.String(20), nullable=False, server_default="open"),
        sa.Column("ai_confidence",   sa.Integer, nullable=True),
        sa.Column("owner_id",        sa.String(36), nullable=True),
    )

    op.create_table(
        "sprint_approvals",
        sa.Column("id",              sa.String(36), primary_key=True),
        sa.Column("created_at",      _ts(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at",      _ts(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False, index=True),
        sa.Column("sprint_id",       sa.String(36), sa.ForeignKey("sprints.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("task_id",         sa.String(36), sa.ForeignKey("sprint_tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kind",            sa.String(40), nullable=False),
        sa.Column("title",           sa.String(500), nullable=False),
        sa.Column("requested_by",    sa.String(255), nullable=False),
        sa.Column("approvers",       sa.JSON, nullable=True),
        sa.Column("status",          sa.String(20), nullable=False, server_default="pending"),
        sa.Column("decided_at",      _ts(), nullable=True),
        sa.Column("decided_by",      sa.String(36), nullable=True),
    )

    op.create_table(
        "migration_releases",
        sa.Column("id",                 sa.String(36), primary_key=True),
        sa.Column("created_at",         _ts(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at",         _ts(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("organization_id",    sa.String(36), nullable=False, index=True),
        sa.Column("project_id",         sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name",               sa.String(255), nullable=False),
        sa.Column("sprint_ids",         sa.JSON, nullable=True),
        sa.Column("stage",              sa.String(40), nullable=False, server_default="planned"),
        sa.Column("target_environment", sa.String(20), nullable=False, server_default="staging"),
        sa.Column("scheduled_for",      _ts(), nullable=True),
        sa.Column("validation_score",   sa.Integer, nullable=False, server_default="0"),
        sa.Column("recon_score",        sa.Integer, nullable=False, server_default="0"),
        sa.Column("rollback_ready",     sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("checklist",          sa.JSON, nullable=True),
    )

    op.create_table(
        "sprint_mapping_nodes",
        sa.Column("id",               sa.String(36), primary_key=True),
        sa.Column("created_at",       _ts(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at",       _ts(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("organization_id",  sa.String(36), nullable=False, index=True),
        sa.Column("project_id",       sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("kind",             sa.String(40), nullable=False),
        sa.Column("label",            sa.String(255), nullable=False),
        sa.Column("owner_id",         sa.String(36), nullable=True),
        sa.Column("agent",            sa.String(64), nullable=True),
        sa.Column("status",           sa.String(40), nullable=False, server_default="pending"),
        sa.Column("validation_score", sa.Integer, nullable=True),
        sa.Column("recon_score",      sa.Integer, nullable=True),
        sa.Column("risk_score",       sa.Integer, nullable=True),
        sa.Column("approval_status",  sa.String(20), nullable=False, server_default="not_required"),
        sa.Column("artifact_count",   sa.Integer, nullable=False, server_default="0"),
        sa.Column("position_x",       sa.Float, nullable=False, server_default="0"),
        sa.Column("position_y",       sa.Float, nullable=False, server_default="0"),
    )

    op.create_table(
        "sprint_mapping_edges",
        sa.Column("id",              sa.String(36), primary_key=True),
        sa.Column("created_at",      _ts(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at",      _ts(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False, index=True),
        sa.Column("project_id",      sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("source_id",       sa.String(36), sa.ForeignKey("sprint_mapping_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_id",       sa.String(36), sa.ForeignKey("sprint_mapping_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status",          sa.String(20), nullable=False, server_default="pending"),
        sa.Column("label",           sa.String(255), nullable=True),
    )

    op.create_table(
        "sprint_agent_executions",
        sa.Column("id",              sa.String(36), primary_key=True),
        sa.Column("created_at",      _ts(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at",      _ts(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False, index=True),
        sa.Column("project_id",      sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("agent_code",      sa.String(64), nullable=False),
        sa.Column("task_id",         sa.String(36), nullable=True),
        sa.Column("status",          sa.String(20), nullable=False, server_default="queued"),
        sa.Column("started_at",      _ts(), nullable=False),
        sa.Column("duration_ms",     sa.Integer, nullable=True),
        sa.Column("retries",         sa.Integer, nullable=False, server_default="0"),
        sa.Column("mode",            sa.String(10), nullable=False, server_default="llm"),
        sa.Column("log",             sa.Text, nullable=True),
    )


def downgrade():
    op.drop_table("sprint_agent_executions")
    op.drop_table("sprint_mapping_edges")
    op.drop_table("sprint_mapping_nodes")
    op.drop_table("migration_releases")
    op.drop_table("sprint_approvals")
    op.drop_table("sprint_risks")
    op.drop_table("sprint_tasks")
    op.drop_table("sprints")
