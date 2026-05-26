"""org_data_encryption_keys: relax org-unique to partial-unique on (org_id WHERE is_active)

DI-C1 follow-up. The original migration `d5e6f7a8b9c0_org_dek_table.py`
declared `organization_id` with `unique=True`, which produced a full
unique index. The rotation flow needs to INSERT a new DEK row for the
same org while the previous row still exists (flipped to
`is_active=False`) so historical decrypts can still walk the inactive
key. The original unique constraint guarantees that flow throws
`IntegrityError` on flush, making `rotate_dek` permanently broken.

This migration replaces the full-column unique with a PARTIAL unique
index on `(organization_id) WHERE is_active = true`. The semantics
operators actually want:
  - at most ONE active DEK per org (enforced by the partial index)
  - any number of inactive historical DEKs may coexist (no constraint)

Postgres path:
  1. Drop the auto-named `org_data_encryption_keys_organization_id_key`
     unique constraint (created by the `unique=True` on the column).
     We use `IF EXISTS` because the constraint name varies on some
     SQLAlchemy versions (`_key` suffix vs `_uniq`).
  2. Create a partial unique index
     `uq_org_dek_active_per_org` on `(organization_id) WHERE is_active`.

SQLite path:
  SQLite doesn't enforce ALTER on unique constraints in a useful way
  (you'd have to rebuild the table). Tests already use create_all
  off the model, so once the model declaration drops `unique=True`
  the in-memory schema is correct. This migration is a no-op there.

Operators with existing duplicate rows: should not exist, since the
old constraint guaranteed at most one row per org. If somehow two
exist, this migration will fail at index creation; clean up by
flipping all-but-the-newest to `is_active=False` first.

Revision ID: 2af2b45b4051
Revises: p7q8r9s0t1u2
Create Date: 2026-05-26
"""

from alembic import op


revision = "2af2b45b4051"
down_revision = "p7q8r9s0t1u2"
branch_labels = None
depends_on = None


_DROP_CANDIDATES = [
    # SQLAlchemy auto-names unique constraints `<table>_<col>_key` on Postgres.
    "org_data_encryption_keys_organization_id_key",
    # Defensive: some local dev DBs may have it under the older name.
    "org_data_encryption_keys_organization_id_uniq",
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite / others: rely on model declaration (unique=True removed)
        # for the in-memory create_all path; no constraint to relax here.
        return

    # 1. Drop the full unique constraint (or matching unique index).
    for name in _DROP_CANDIDATES:
        op.execute(f'ALTER TABLE org_data_encryption_keys DROP CONSTRAINT IF EXISTS "{name}"')
        op.execute(f'DROP INDEX IF EXISTS "{name}"')

    # 2. Create the partial unique index — at most one active DEK per org.
    op.execute(
        'CREATE UNIQUE INDEX IF NOT EXISTS "uq_org_dek_active_per_org" '
        'ON "org_data_encryption_keys" ("organization_id") '
        'WHERE is_active = true'
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute('DROP INDEX IF EXISTS "uq_org_dek_active_per_org"')
    # Recreate the original full unique constraint. Only safe if no
    # historical inactive rows exist for the same org — operators
    # downgrading after a rotation must dedupe manually first.
    op.execute(
        'ALTER TABLE org_data_encryption_keys '
        'ADD CONSTRAINT org_data_encryption_keys_organization_id_key '
        'UNIQUE (organization_id)'
    )
