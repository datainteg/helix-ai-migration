"""connection_encrypted_config

Add encrypted_config + config_masked columns to source_connections and
target_connections so connector credentials can be persisted server-side
with envelope encryption. Existing rows are unaffected (columns are nullable).

Revision ID: g8h9i0j1k2l3
Revises: f7a8b9c0d1e2
Create Date: 2026-05-25

"""
from alembic import op
import sqlalchemy as sa


revision = "g8h9i0j1k2l3"
down_revision = "f7a8b9c0d1e2"


def upgrade():
    with op.batch_alter_table("source_connections") as batch:
        batch.add_column(sa.Column("encrypted_config", sa.Text(), nullable=True))
        batch.add_column(sa.Column("config_masked", sa.String(500), nullable=True))

    with op.batch_alter_table("target_connections") as batch:
        batch.add_column(sa.Column("encrypted_config", sa.Text(), nullable=True))
        batch.add_column(sa.Column("config_masked", sa.String(500), nullable=True))


def downgrade():
    with op.batch_alter_table("target_connections") as batch:
        batch.drop_column("config_masked")
        batch.drop_column("encrypted_config")

    with op.batch_alter_table("source_connections") as batch:
        batch.drop_column("config_masked")
        batch.drop_column("encrypted_config")
