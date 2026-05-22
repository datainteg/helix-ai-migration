"""agent_tables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-23

"""
from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"


def upgrade():
    # agent_definitions
    op.create_table("agent_definitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("agent_type", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("schema_version", sa.String(20), server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # prompt_templates
    op.create_table("prompt_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("agent_type", sa.String(100), nullable=False),
        sa.Column("template", sa.Text, nullable=False),
        sa.Column("status", sa.String(50), server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # prompt_versions
    op.create_table("prompt_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("template_id", sa.String(36), sa.ForeignKey("prompt_templates.id"), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # agent_tasks
    op.create_table("agent_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=False, index=True),
        sa.Column("agent_type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), server_default="created"),
        sa.Column("input_payload", sa.Text, nullable=True),
        sa.Column("prompt_template_id", sa.String(36), sa.ForeignKey("prompt_templates.id"), nullable=True),
        sa.Column("prompt_version_id", sa.String(36), sa.ForeignKey("prompt_versions.id"), nullable=True),
        sa.Column("llm_provider_id", sa.String(36), sa.ForeignKey("llm_providers.id"), nullable=True),
        sa.Column("llm_model", sa.String(100), nullable=True),
        sa.Column("token_usage", sa.String(50), nullable=True),
        sa.Column("started_at", sa.String(50), nullable=True),
        sa.Column("finished_at", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # agent_outputs
    op.create_table("agent_outputs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("agent_tasks.id"), nullable=False),
        sa.Column("schema_name", sa.String(100), nullable=False),
        sa.Column("schema_version", sa.String(20), server_default="1.0"),
        sa.Column("output_payload", sa.Text, nullable=False),
        sa.Column("confidence_score", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("agent_outputs")
    op.drop_table("agent_tasks")
    op.drop_table("prompt_versions")
    op.drop_table("prompt_templates")
    op.drop_table("agent_definitions")
