"""composite indexes for high-traffic query paths

Revision ID: b2c3d4e5f6a8
Revises: a1b2c3d4e5f6
Create Date: 2026-05-23

"""
from alembic import op

revision = "b2c3d4e5f6a8"
down_revision = "a1b2c3d4e5f6"


def upgrade():
    op.create_index("ix_workflow_runs_org_created", "workflow_runs", ["organization_id", "created_at"], postgresql_using="btree")
    op.create_index("ix_audit_logs_org_created", "audit_logs", ["organization_id", "created_at"], postgresql_using="btree")
    op.create_index("ix_artifacts_org_project", "code_artifacts", ["organization_id", "project_id"], postgresql_using="btree")


def downgrade():
    op.drop_index("ix_artifacts_org_project", table_name="code_artifacts")
    op.drop_index("ix_audit_logs_org_created", table_name="audit_logs")
    op.drop_index("ix_workflow_runs_org_created", table_name="workflow_runs")
