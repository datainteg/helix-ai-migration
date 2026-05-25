"""knowledge_docs

Knowledge-base table for the RAG layer over enterprise docs.

Revision ID: o6p7q8r9s0t1
Revises: n5o6p7q8r9s0
Create Date: 2026-05-25
"""

from alembic import op
import sqlalchemy as sa


revision = "o6p7q8r9s0t1"
down_revision = "n5o6p7q8r9s0"


def upgrade():
    op.create_table(
        "knowledge_docs",
        sa.Column("id",              sa.String(36), primary_key=True),
        sa.Column("created_at",      sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at",      sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False, index=True),
        sa.Column("title",           sa.String(255), nullable=False),
        sa.Column("source_url",      sa.String(500), nullable=True),
        sa.Column("tags",            sa.String(500), nullable=True),
        sa.Column("content",         sa.Text, nullable=False),
        sa.Column("content_length",  sa.Integer, server_default="0", nullable=False),
    )


def downgrade():
    op.drop_table("knowledge_docs")
