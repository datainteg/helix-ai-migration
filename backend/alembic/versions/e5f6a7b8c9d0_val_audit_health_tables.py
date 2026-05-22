"""val_audit_health_tables

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-23

"""
from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"


def upgrade():
    for name, cols in [
        ("validation_rules", [("project_id", True), ("rule_type", False), ("target_ref", True), ("definition", True), ("status", False, "active")]),
        ("validation_runs", [("project_id", True), ("started_by", False), ("status", False, "pending"), ("started_at", True), ("finished_at", True)]),
        ("validation_results", [("run_id", False), ("rule_id", False), ("status", False), ("observed_value", True), ("expected_value", True)]),
        ("recon_runs", [("project_id", True), ("source_ref", True), ("target_ref", True), ("status", False, "pending")]),
        ("recon_results", [("run_id", False), ("result_type", False), ("summary", True), ("mismatch_count", True), ("details_ref", True)]),
        ("audit_logs", [("organization_id", True), ("actor_id", True), ("action", False), ("entity_type", True), ("entity_id", True), ("metadata", True), ("ip_address", True), ("user_agent", True)]),
        ("system_health_checks", [("component", False), ("status", False), ("message", True)]),
    ]:
        table_cols = [
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        ]
        for c in cols:
            col = sa.Column(c[0], sa.Text if c[0] in ("definition", "summary", "metadata") else sa.String(255), nullable=not c[1])
            if len(c) > 2:
                col = sa.Column(c[0], sa.Text if c[0] in ("definition", "summary", "metadata") else sa.String(255), server_default=c[2] if c[1] else None, nullable=c[1])
            table_cols.append(col)
        op.create_table(name, *table_cols)


def downgrade():
    for t in ["system_health_checks", "audit_logs", "recon_results", "recon_runs", "validation_results", "validation_runs", "validation_rules"]:
        op.drop_table(t)
