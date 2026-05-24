"""user_preferences

Adds `users.preferences` (JSON, nullable) so per-user UI tweaks
(theme, density, font size, surface tint, primary color, notification
toggles) can sync across browsers/devices instead of living only in
localStorage.

Revision ID: h9i0j1k2l3m4
Revises: g8h9i0j1k2l3
Create Date: 2026-05-25
"""

from alembic import op
import sqlalchemy as sa


revision = "h9i0j1k2l3m4"
down_revision = "g8h9i0j1k2l3"


def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("preferences", sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table("users") as batch:
        batch.drop_column("preferences")
