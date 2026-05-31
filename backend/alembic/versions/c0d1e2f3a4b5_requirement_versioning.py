"""requirement versioning: migration_requirements.root_id

Adds a nullable root_id so editing a requirement can create a new version row
that shares the original's root_id (version-chain). Legacy rows keep root_id
NULL and are treated as their own root by the service layer.

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
"""
from alembic import op
import sqlalchemy as sa

revision = "c0d1e2f3a4b5"
down_revision = "b9c0d1e2f3a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("migration_requirements", sa.Column("root_id", sa.String(length=36), nullable=True))
    op.create_index("ix_migration_requirements_root_id", "migration_requirements", ["root_id"])
    # Backfill: existing rows become their own root so grouping is stable.
    op.execute("UPDATE migration_requirements SET root_id = id WHERE root_id IS NULL")


def downgrade() -> None:
    op.drop_index("ix_migration_requirements_root_id", table_name="migration_requirements")
    op.drop_column("migration_requirements", "root_id")
