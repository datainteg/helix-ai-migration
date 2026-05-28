"""M-015: widen recon_results.mismatch_count to BigInteger

Row-count reconciliation stores ``mismatch_count = abs(source - target)``.
On real migrations the row counts (and therefore the diff) routinely exceed
2^31, which overflows a 32-bit Integer column on INSERT. Widen the column to
BigInteger (64-bit) to match the model.

Postgres: ``ALTER COLUMN ... TYPE BIGINT`` is an in-place metadata change for
a widening cast and does not rewrite the table. SQLite (test backend) does not
distinguish INTEGER widths and stores all integers as 64-bit dynamic types, so
the ``alter_column`` is a structural no-op there — guarded accordingly.

Revision ID: t1u2v3w4x5y6
Revises: s0t1u2v3w4x5
Create Date: 2026-05-28
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "t1u2v3w4x5y6"
down_revision = "s0t1u2v3w4x5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.alter_column(
            "recon_results",
            "mismatch_count",
            existing_type=sa.Integer(),
            type_=sa.BigInteger(),
            existing_nullable=True,
        )
    # SQLite: integer affinity is already 64-bit dynamic — no-op.


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.alter_column(
            "recon_results",
            "mismatch_count",
            existing_type=sa.BigInteger(),
            type_=sa.Integer(),
            existing_nullable=True,
        )
