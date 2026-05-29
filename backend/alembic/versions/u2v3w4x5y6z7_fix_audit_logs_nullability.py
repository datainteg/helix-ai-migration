"""Fix audit_logs column nullability to match the AuditLog model

A prior migration created ``audit_logs`` with NOT NULL constraints that
contradict ``app/models/observability.py`` (which marks everything except
``organization_id`` and ``action`` as nullable). The mismatch made
``write_audit`` raise NotNullViolation whenever a caller omitted optional
fields — most visibly the ``first_admin_created`` event, which has no
``user_agent``/``metadata`` and therefore broke first-admin provisioning
with a 500 (and left a half-committed admin behind).

This realigns the DB to the model:
  - DROP NOT NULL on actor_id, entity_type, entity_id, metadata,
    ip_address, user_agent
  - SET NOT NULL on action (model: nullable=False)

Revision ID: u2v3w4x5y6z7
Revises: t1u2v3w4x5y6
Create Date: 2026-05-29
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "u2v3w4x5y6z7"
down_revision = "t1u2v3w4x5y6"
branch_labels = None
depends_on = None

_DROP_NOT_NULL = [
    ("actor_id", sa.String(length=36)),
    ("entity_type", sa.String(length=100)),
    ("entity_id", sa.String(length=36)),
    ("metadata", sa.Text()),
    ("ip_address", sa.String(length=50)),
    ("user_agent", sa.String(length=255)),
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # Test backends build tables from the model, which is already correct.
        return
    for col, coltype in _DROP_NOT_NULL:
        op.alter_column("audit_logs", col, existing_type=coltype, nullable=True)
    op.alter_column("audit_logs", "action", existing_type=sa.String(length=100), nullable=False)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.alter_column("audit_logs", "action", existing_type=sa.String(length=100), nullable=True)
    for col, coltype in _DROP_NOT_NULL:
        op.alter_column("audit_logs", col, existing_type=coltype, nullable=False)
