"""workflow_steps unique (workflow_run_id, step_order)

Adds a unique constraint so the worker can upsert step rows on retry instead
of inserting a duplicate. Without this, Temporal activity retries would leave
the workflow_steps table with one row per attempt — first idempotency gap
surfaced by the 2026-05-25 code review.

Revision ID: l3m4n5o6p7q8
Revises: k2l3m4n5o6p7
Create Date: 2026-05-25
"""

from alembic import op


revision = "l3m4n5o6p7q8"
down_revision = "k2l3m4n5o6p7"


def upgrade():
    # Best-effort: collapse pre-existing duplicates so the constraint can be
    # added without manual data cleanup.
    op.execute(
        """
        DELETE FROM workflow_steps a
        USING workflow_steps b
        WHERE a.id > b.id
          AND a.workflow_run_id = b.workflow_run_id
          AND a.step_order      = b.step_order
        """
    )
    op.create_unique_constraint(
        "uq_workflow_steps_run_order",
        "workflow_steps",
        ["workflow_run_id", "step_order"],
    )


def downgrade():
    op.drop_constraint(
        "uq_workflow_steps_run_order",
        "workflow_steps",
        type_="unique",
    )
