"""cutover + llm_usage_records + org_cost_limits + rollback_artifact_id

Top-5 production features land in a single migration so operators can apply
them with one `alembic upgrade head`:

  - migration_cutovers      cutover orchestration state machine
  - llm_usage_records       per-call LLM cost + token ledger
  - org_cost_limits         per-org daily/monthly USD cap
  - code_artifacts.rollback_artifact_id   self-FK linking forward → reverse

Revision ID: m4n5o6p7q8r9
Revises: l3m4n5o6p7q8
Create Date: 2026-05-25
"""

from alembic import op
import sqlalchemy as sa


revision = "m4n5o6p7q8r9"
down_revision = "l3m4n5o6p7q8"


def upgrade():
    # ── migration_cutovers ────────────────────────────────────────────
    op.create_table(
        "migration_cutovers",
        sa.Column("id",               sa.String(36), primary_key=True),
        sa.Column("created_at",       sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at",       sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("organization_id",  sa.String(36), nullable=False, index=True),
        sa.Column("project_id",       sa.String(36), sa.ForeignKey("projects.id"), nullable=False, index=True),
        sa.Column("workflow_id",      sa.String(255), nullable=True),
        sa.Column("source_ref",       sa.String(255), nullable=False),
        sa.Column("target_ref",       sa.String(255), nullable=False),
        sa.Column("state",            sa.String(20), nullable=False, server_default="bulk"),
        sa.Column("bulk_started_at",  sa.DateTime(timezone=True), nullable=True),
        sa.Column("tail_started_at",  sa.DateTime(timezone=True), nullable=True),
        sa.Column("freeze_started_at",sa.DateTime(timezone=True), nullable=True),
        sa.Column("diff_started_at",  sa.DateTime(timezone=True), nullable=True),
        sa.Column("flip_started_at",  sa.DateTime(timezone=True), nullable=True),
        sa.Column("done_at",          sa.DateTime(timezone=True), nullable=True),
        sa.Column("rolled_back_at",   sa.DateTime(timezone=True), nullable=True),
        sa.Column("diff_summary",     sa.Text, nullable=True),
        sa.Column("notes",            sa.Text, nullable=True),
    )

    # ── llm_usage_records ─────────────────────────────────────────────
    op.create_table(
        "llm_usage_records",
        sa.Column("id",              sa.String(36), primary_key=True),
        sa.Column("created_at",      sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at",      sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False, index=True),
        sa.Column("project_id",      sa.String(36), nullable=True, index=True),
        sa.Column("workflow_id",     sa.String(255), nullable=True, index=True),
        sa.Column("agent_name",      sa.String(100), nullable=True, index=True),
        sa.Column("provider_type",   sa.String(50), nullable=False),
        sa.Column("model",           sa.String(100), nullable=False),
        sa.Column("input_tokens",    sa.Integer, server_default="0", nullable=False),
        sa.Column("output_tokens",   sa.Integer, server_default="0", nullable=False),
        sa.Column("cost_usd",        sa.Float,   server_default="0.0", nullable=False),
        sa.Column("step_id",         sa.String(36), sa.ForeignKey("workflow_steps.id"), nullable=True),
    )
    # Window queries (last-N-days rollup) are the hot path; index helps.
    op.create_index(
        "ix_llm_usage_records_org_created",
        "llm_usage_records",
        ["organization_id", "created_at"],
    )

    # ── org_cost_limits ───────────────────────────────────────────────
    op.create_table(
        "org_cost_limits",
        sa.Column("id",               sa.String(36), primary_key=True),
        sa.Column("created_at",       sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at",       sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("organization_id",  sa.String(36), nullable=False, unique=True, index=True),
        sa.Column("daily_usd_cap",    sa.Float, server_default="0.0", nullable=False),
        sa.Column("monthly_usd_cap",  sa.Float, server_default="0.0", nullable=False),
        sa.Column("enforcement",      sa.String(20), server_default="hard", nullable=False),
    )

    # ── code_artifacts.rollback_artifact_id ───────────────────────────
    op.add_column(
        "code_artifacts",
        sa.Column("rollback_artifact_id", sa.String(36), nullable=True),
    )
    op.create_foreign_key(
        "fk_code_artifacts_rollback",
        "code_artifacts", "code_artifacts",
        ["rollback_artifact_id"], ["id"],
    )


def downgrade():
    op.drop_constraint("fk_code_artifacts_rollback", "code_artifacts", type_="foreignkey")
    op.drop_column("code_artifacts", "rollback_artifact_id")
    op.drop_table("org_cost_limits")
    op.drop_index("ix_llm_usage_records_org_created", table_name="llm_usage_records")
    op.drop_table("llm_usage_records")
    op.drop_table("migration_cutovers")
