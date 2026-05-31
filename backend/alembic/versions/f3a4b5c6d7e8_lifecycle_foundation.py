"""stage-gated migration lifecycle foundation

Additive only. Adds:
- projects: alias (+backfill, unique), current_stage, lifecycle_status,
  stage_progress_percent, approved_at, closed_at, use_stage_gated_lifecycle
- sprints: sprint_alias, progress rollups, risk_level, created_from_artifact_id,
  approved_by_user_id, approved_at
- new tables: migration_stages, stage_transition_logs, migration_artifacts,
  migration_artifact_versions, migration_artifact_reviews,
  migration_artifact_comments, validation_evidence, recon_reports,
  signoff_requests, developer_workspaces, generated_code_artifacts

No drops, no row-level production data.

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
"""
import random
from alembic import op
import sqlalchemy as sa

revision = "f3a4b5c6d7e8"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def _base():
    """Shared BaseModel columns (id + timestamps)."""
    return [
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    # ── projects: lifecycle columns ─────────────────────────────────
    op.add_column("projects", sa.Column("alias", sa.String(length=20), nullable=True))
    op.add_column("projects", sa.Column("current_stage", sa.String(length=40), nullable=True))
    op.add_column("projects", sa.Column("lifecycle_status", sa.String(length=20), nullable=False, server_default="not_started"))
    op.add_column("projects", sa.Column("stage_progress_percent", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("projects", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("projects", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("projects", sa.Column("use_stage_gated_lifecycle", sa.Boolean(), nullable=False, server_default="false"))

    # Backfill alias (HXM-NNNNNN) for existing rows, unique across the batch.
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id FROM projects WHERE alias IS NULL")).fetchall()
    used: set[str] = set(
        r[0] for r in conn.execute(sa.text("SELECT alias FROM projects WHERE alias IS NOT NULL")).fetchall()
    )
    for r in rows:
        while True:
            alias = f"HXM-{random.randint(0, 999999):06d}"
            if alias not in used:
                used.add(alias)
                break
        conn.execute(sa.text("UPDATE projects SET alias = :a WHERE id = :i"), {"a": alias, "i": r[0]})
    op.create_index("uq_projects_alias", "projects", ["alias"], unique=True)

    # ── sprints: lifecycle columns ──────────────────────────────────
    op.add_column("sprints", sa.Column("sprint_alias", sa.String(length=40), nullable=True))
    op.add_column("sprints", sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("sprints", sa.Column("validation_progress_percent", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("sprints", sa.Column("recon_progress_percent", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("sprints", sa.Column("risk_level", sa.String(length=20), nullable=True))
    op.add_column("sprints", sa.Column("created_from_artifact_id", sa.String(length=36), nullable=True))
    op.add_column("sprints", sa.Column("approved_by_user_id", sa.String(length=36), nullable=True))
    op.add_column("sprints", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))

    # ── migration_stages ────────────────────────────────────────────
    op.create_table(
        "migration_stages", *_base(),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_key", sa.String(length=40), nullable=False),
        sa.Column("stage_name", sa.String(length=120), nullable=False),
        sa.Column("stage_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="not_started"),
        sa.Column("assigned_agent", sa.String(length=80), nullable=True),
        sa.Column("is_optional", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_for_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_artifact_id", sa.String(length=36), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.UniqueConstraint("project_id", "stage_key", name="uq_migration_stage_project_key"),
    )
    op.create_index("ix_migration_stages_org", "migration_stages", ["organization_id"])
    op.create_index("ix_migration_stages_project", "migration_stages", ["project_id"])
    op.create_index("ix_migration_stages_key", "migration_stages", ["stage_key"])
    op.create_index("ix_migration_stages_status", "migration_stages", ["status"])

    # ── stage_transition_logs ───────────────────────────────────────
    op.create_table(
        "stage_transition_logs", *_base(),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_id", sa.String(length=36), sa.ForeignKey("migration_stages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", sa.String(length=30), nullable=True),
        sa.Column("to_status", sa.String(length=30), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
    )
    op.create_index("ix_stage_transition_logs_org", "stage_transition_logs", ["organization_id"])
    op.create_index("ix_stage_transition_logs_project", "stage_transition_logs", ["project_id"])
    op.create_index("ix_stage_transition_logs_stage", "stage_transition_logs", ["stage_id"])

    # ── migration_artifacts ─────────────────────────────────────────
    op.create_table(
        "migration_artifacts", *_base(),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_id", sa.String(length=36), sa.ForeignKey("migration_stages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("artifact_type", sa.String(length=60), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("current_version_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("created_by_agent", sa.String(length=80), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("approved_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_migration_artifacts_org", "migration_artifacts", ["organization_id"])
    op.create_index("ix_migration_artifacts_project", "migration_artifacts", ["project_id"])
    op.create_index("ix_migration_artifacts_stage", "migration_artifacts", ["stage_id"])
    op.create_index("ix_migration_artifacts_type", "migration_artifacts", ["artifact_type"])
    op.create_index("ix_migration_artifacts_status", "migration_artifacts", ["status"])

    # ── migration_artifact_versions ─────────────────────────────────
    op.create_table(
        "migration_artifact_versions", *_base(),
        sa.Column("artifact_id", sa.String(length=36), sa.ForeignKey("migration_artifacts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=True),
        sa.Column("content_json", sa.JSON(), nullable=True),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column("created_by_type", sa.String(length=20), nullable=False, server_default="agent"),
        sa.Column("created_by_agent", sa.String(length=80), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("source_version_id", sa.String(length=36), nullable=True),
    )
    op.create_index("ix_migration_artifact_versions_artifact", "migration_artifact_versions", ["artifact_id"])
    op.create_index("ix_migration_artifact_versions_artifact_ver", "migration_artifact_versions", ["artifact_id", "version_number"])

    # ── migration_artifact_reviews ──────────────────────────────────
    op.create_table(
        "migration_artifact_reviews", *_base(),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("artifact_id", sa.String(length=36), sa.ForeignKey("migration_artifacts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("artifact_version_id", sa.String(length=36), sa.ForeignKey("migration_artifact_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer_user_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("comments", sa.Text(), nullable=True),
    )
    op.create_index("ix_migration_artifact_reviews_org", "migration_artifact_reviews", ["organization_id"])
    op.create_index("ix_migration_artifact_reviews_project", "migration_artifact_reviews", ["project_id"])
    op.create_index("ix_migration_artifact_reviews_artifact", "migration_artifact_reviews", ["artifact_id"])

    # ── migration_artifact_comments ─────────────────────────────────
    op.create_table(
        "migration_artifact_comments", *_base(),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("artifact_id", sa.String(length=36), sa.ForeignKey("migration_artifacts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("artifact_version_id", sa.String(length=36), nullable=True),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("comment", sa.Text(), nullable=False),
    )
    op.create_index("ix_migration_artifact_comments_org", "migration_artifact_comments", ["organization_id"])
    op.create_index("ix_migration_artifact_comments_project", "migration_artifact_comments", ["project_id"])
    op.create_index("ix_migration_artifact_comments_artifact", "migration_artifact_comments", ["artifact_id"])

    # ── validation_evidence ─────────────────────────────────────────
    op.create_table(
        "validation_evidence", *_base(),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sprint_id", sa.String(length=36), nullable=True),
        sa.Column("artifact_id", sa.String(length=36), nullable=True),
        sa.Column("uploaded_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("evidence_type", sa.String(length=60), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        sa.Column("content_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="uploaded"),
        sa.Column("reviewed_by_agent", sa.String(length=80), nullable=True),
        sa.Column("reviewed_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("review_summary", sa.Text(), nullable=True),
    )
    op.create_index("ix_validation_evidence_org", "validation_evidence", ["organization_id"])
    op.create_index("ix_validation_evidence_project", "validation_evidence", ["project_id"])
    op.create_index("ix_validation_evidence_sprint", "validation_evidence", ["sprint_id"])
    op.create_index("ix_validation_evidence_status", "validation_evidence", ["status"])

    # ── recon_reports ───────────────────────────────────────────────
    op.create_table(
        "recon_reports", *_base(),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sprint_id", sa.String(length=36), nullable=True),
        sa.Column("report_type", sa.String(length=60), nullable=False, server_default="business"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("source_summary_json", sa.JSON(), nullable=True),
        sa.Column("target_summary_json", sa.JSON(), nullable=True),
        sa.Column("mismatch_summary_json", sa.JSON(), nullable=True),
        sa.Column("business_rules_json", sa.JSON(), nullable=True),
        sa.Column("report_markdown", sa.Text(), nullable=True),
        sa.Column("report_pdf_path", sa.String(length=500), nullable=True),
        sa.Column("generated_by_agent", sa.String(length=80), nullable=True),
        sa.Column("approved_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_recon_reports_org", "recon_reports", ["organization_id"])
    op.create_index("ix_recon_reports_project", "recon_reports", ["project_id"])
    op.create_index("ix_recon_reports_sprint", "recon_reports", ["sprint_id"])
    op.create_index("ix_recon_reports_status", "recon_reports", ["status"])

    # ── signoff_requests ────────────────────────────────────────────
    op.create_table(
        "signoff_requests", *_base(),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recon_report_id", sa.String(length=36), nullable=True),
        sa.Column("recipient_email", sa.String(length=255), nullable=True),
        sa.Column("subject", sa.String(length=500), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("attachment_paths_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
    )
    op.create_index("ix_signoff_requests_org", "signoff_requests", ["organization_id"])
    op.create_index("ix_signoff_requests_project", "signoff_requests", ["project_id"])
    op.create_index("ix_signoff_requests_status", "signoff_requests", ["status"])

    # ── developer_workspaces ────────────────────────────────────────
    op.create_table(
        "developer_workspaces", *_base(),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sprint_id", sa.String(length=36), nullable=True),
        sa.Column("workspace_alias", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="created"),
        sa.Column("workspace_type", sa.String(length=30), nullable=False, server_default="artifact_only"),
        sa.Column("container_name", sa.String(length=120), nullable=True),
        sa.Column("workspace_url", sa.String(length=500), nullable=True),
        sa.Column("storage_path", sa.String(length=500), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
    )
    op.create_index("ix_developer_workspaces_org", "developer_workspaces", ["organization_id"])
    op.create_index("ix_developer_workspaces_project", "developer_workspaces", ["project_id"])
    op.create_index("ix_developer_workspaces_sprint", "developer_workspaces", ["sprint_id"])

    # ── generated_code_artifacts ────────────────────────────────────
    op.create_table(
        "generated_code_artifacts", *_base(),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sprint_id", sa.String(length=36), nullable=True),
        sa.Column("stage_id", sa.String(length=36), nullable=True),
        sa.Column("artifact_id", sa.String(length=36), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=30), nullable=True),
        sa.Column("language", sa.String(length=40), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("generated_by_agent", sa.String(length=80), nullable=True),
        sa.Column("reviewed_by_user_id", sa.String(length=36), nullable=True),
    )
    op.create_index("ix_generated_code_artifacts_org", "generated_code_artifacts", ["organization_id"])
    op.create_index("ix_generated_code_artifacts_project", "generated_code_artifacts", ["project_id"])
    op.create_index("ix_generated_code_artifacts_sprint", "generated_code_artifacts", ["sprint_id"])
    op.create_index("ix_generated_code_artifacts_status", "generated_code_artifacts", ["status"])


def downgrade() -> None:
    for t in (
        "generated_code_artifacts", "developer_workspaces", "signoff_requests",
        "recon_reports", "validation_evidence", "migration_artifact_comments",
        "migration_artifact_reviews", "migration_artifact_versions",
        "migration_artifacts", "stage_transition_logs", "migration_stages",
    ):
        op.drop_table(t)
    for c in ("sprint_alias", "progress_percent", "validation_progress_percent",
              "recon_progress_percent", "risk_level", "created_from_artifact_id",
              "approved_by_user_id", "approved_at"):
        op.drop_column("sprints", c)
    op.drop_index("uq_projects_alias", table_name="projects")
    for c in ("use_stage_gated_lifecycle", "closed_at", "approved_at",
              "stage_progress_percent", "lifecycle_status", "current_stage", "alias"):
        op.drop_column("projects", c)
