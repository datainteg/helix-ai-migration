"""merge wave-3 dual heads (DEK partial-unique + extra_config encryption)

Two wave-3 migrations both chained their down_revision to p7q8r9s0t1u2:
  - 2af2b45b4051 (DEK partial-unique active per org)
  - q8r9s0t1u2v3 (extra_config secret encryption)

`alembic upgrade head` refuses to run with multiple heads. This empty
merge revision unifies them into a single head so backend-init can
apply the chain on first start.

No-op upgrade/downgrade — pure metadata reconciliation.

Revision ID: r9s0t1u2v3w4
Revises: 2af2b45b4051, q8r9s0t1u2v3
Create Date: 2026-05-26
"""

from __future__ import annotations

# revision identifiers, used by Alembic.
revision = "r9s0t1u2v3w4"
down_revision = ("2af2b45b4051", "q8r9s0t1u2v3")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
