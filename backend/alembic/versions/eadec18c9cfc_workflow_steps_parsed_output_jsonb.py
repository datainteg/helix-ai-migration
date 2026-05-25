"""workflow_steps.parsed_output_json: Text -> JSONB (with junk-row guard)

DI-C4 from REVIEW_DATA_INTEGRITY.md.

The original creation migration (f6a7b8c9d0e1) declared
`parsed_output_json` as sa.Text, but the SQLAlchemy model declares
JSONB. SQLAlchemy serializes dicts on write and the column stores a
JSON string; reads return the raw string instead of a parsed dict.

This migration:
  - On Postgres: ALTER ... USING parsed_output_json::jsonb with a
    CASE that NULLs rows whose value isn't valid JSON (the dict-repr
    rows pre-fix). Safe to re-run.
  - On SQLite (tests + dev fallback): no-op. SQLite stores JSON as
    TEXT either way and the model's JSONB column reads/writes via the
    JSON SQL type fallback.

Revision ID: eadec18c9cfc
Revises: o6p7q8r9s0t1
Create Date: 2026-05-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "eadec18c9cfc"
down_revision = "o6p7q8r9s0t1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite / others: model's JSONB column maps to TEXT in CREATE,
        # so no schema change is required for tests to pass.
        return

    # Step 1: clear rows whose stored text is NOT valid JSON so the cast
    # below doesn't blow up the whole migration on a single bad row.
    # The leading-char heuristic catches dict-repr rows ("{'key': ...}")
    # which start with `{` but contain single quotes (invalid JSON).
    op.execute(
        """
        UPDATE workflow_steps
           SET parsed_output_json = NULL
         WHERE parsed_output_json IS NOT NULL
           AND (
             parsed_output_json !~ '^\\s*[\\{\\[]'
             OR parsed_output_json ~ E'^\\s*\\{[^"]*''[^"]*'
           )
        """
    )

    # Step 2: convert column. The remaining rows are valid JSON or NULL.
    op.execute(
        """
        ALTER TABLE workflow_steps
        ALTER COLUMN parsed_output_json TYPE JSONB
        USING parsed_output_json::jsonb
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        """
        ALTER TABLE workflow_steps
        ALTER COLUMN parsed_output_json TYPE TEXT
        USING parsed_output_json::text
        """
    )
