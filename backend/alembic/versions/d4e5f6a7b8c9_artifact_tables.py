"""artifact_tables

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-23

"""
from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"


def upgrade():
    op.create_table("code_artifacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False, index=True),
        sa.Column("project_id", sa.String(36), nullable=False, index=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_type", sa.String(20), nullable=False),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(50), server_default="uploaded"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table("code_artifact_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("artifact_id", sa.String(36), sa.ForeignKey("code_artifacts.id"), nullable=False),
        sa.Column("version_number", sa.String(20), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("generated_by_agent", sa.String(100), nullable=True),
        sa.Column("llm_provider_id", sa.String(36), sa.ForeignKey("llm_providers.id"), nullable=True),
        sa.Column("llm_model", sa.String(100), nullable=True),
        sa.Column("change_summary", sa.Text, nullable=True),
        sa.Column("approval_status", sa.String(50), server_default="draft"),
        sa.Column("approved_by", sa.String(36), nullable=True),
        sa.Column("approved_at", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table("artifact_dependencies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("artifact_id", sa.String(36), sa.ForeignKey("code_artifacts.id"), nullable=False),
        sa.Column("depends_on_artifact_id", sa.String(36), sa.ForeignKey("code_artifacts.id"), nullable=False),
        sa.Column("dependency_type", sa.String(50), server_default="imports"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table("artifact_lineage",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_artifact_id", sa.String(36), sa.ForeignKey("code_artifacts.id"), nullable=False),
        sa.Column("generated_artifact_id", sa.String(36), sa.ForeignKey("code_artifacts.id"), nullable=False),
        sa.Column("conversion_run_id", sa.String(100), nullable=True),
        sa.Column("relationship_type", sa.String(50), server_default="generated_from"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table("code_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("artifact_version_id", sa.String(36), sa.ForeignKey("code_artifact_versions.id"), nullable=False),
        sa.Column("review_type", sa.String(50), server_default="ai_review"),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("findings", sa.Text, nullable=True),
        sa.Column("reviewer_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table("artifact_approvals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("artifact_version_id", sa.String(36), sa.ForeignKey("code_artifact_versions.id"), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("approved_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("artifact_approvals")
    op.drop_table("code_reviews")
    op.drop_table("artifact_lineage")
    op.drop_table("artifact_dependencies")
    op.drop_table("code_artifact_versions")
    op.drop_table("code_artifacts")
