"""llm_provider_extra_config

Adds `llm_providers.extra_config` (JSON, nullable) to hold provider-specific
config that doesn't fit `base_url`:
  - Bedrock: { "aws_region": "us-east-1", "aws_access_key_id": "...", "aws_secret_access_key": "..." }
            (or rely on instance-role / env)
  - Vertex AI: { "gcp_project": "my-project", "gcp_location": "us-central1" }
  - Azure OpenAI: { "azure_endpoint": "https://x.openai.azure.com",
                    "api_version": "2026-01-01", "deployment_name": "..." }

Anything not listed is left as raw JSON for the adapter to interpret.

Revision ID: i0j1k2l3m4n5
Revises: h9i0j1k2l3m4
Create Date: 2026-05-25
"""

from alembic import op
import sqlalchemy as sa


revision = "i0j1k2l3m4n5"
down_revision = "h9i0j1k2l3m4"


def upgrade():
    with op.batch_alter_table("llm_providers") as batch:
        batch.add_column(sa.Column("extra_config", sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table("llm_providers") as batch:
        batch.drop_column("extra_config")
