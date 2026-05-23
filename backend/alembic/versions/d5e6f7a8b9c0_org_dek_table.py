"""org_data_encryption_keys table

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-05-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "d5e6f7a8b9c0"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "org_data_encryption_keys",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=False), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("encrypted_dek", sa.String(512), nullable=False),
        sa.Column("key_version", sa.String(50), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_org_dek_org_id", "org_data_encryption_keys", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_org_dek_org_id", "org_data_encryption_keys")
    op.drop_table("org_data_encryption_keys")
