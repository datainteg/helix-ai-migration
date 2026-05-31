"""lifecycle review hardening

Additive follow-up to f3a4b5c6d7e8 addressing adversarial-review findings:
  * migration_stages.submitted_for_review_by — records WHO submitted a stage
    for review, so approve_stage can enforce separation of duties (the
    submitter may not self-approve unless they are an admin/super_admin).
  * UNIQUE(artifact_id, version_number) on migration_artifact_versions —
    closes the read-then-write race in _next_version_number (concurrent
    create/edit could mint duplicate version numbers; the DB now rejects it
    and the service retries).

Additive only: one nullable column + one unique constraint. No drops.

Revision ID: f4a5b6c7d8e9
Revises: f3a4b5c6d7e8
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa

revision = "f4a5b6c7d8e9"
down_revision = "f3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "migration_stages",
        sa.Column("submitted_for_review_by", sa.String(length=36), nullable=True),
    )
    op.create_unique_constraint(
        "uq_migration_artifact_versions_artifact_ver",
        "migration_artifact_versions",
        ["artifact_id", "version_number"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_migration_artifact_versions_artifact_ver",
        "migration_artifact_versions",
        type_="unique",
    )
    op.drop_column("migration_stages", "submitted_for_review_by")
