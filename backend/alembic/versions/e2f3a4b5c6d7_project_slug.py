"""project slug: projects.slug (readable URLs)

Adds a nullable, indexed slug and backfills existing rows from their name
(lowercased, hyphenated; -2/-3 suffix on collision within an org). Resolution
in the service accepts slug OR id, so legacy UUID links keep working.

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
"""
import re
from alembic import op
import sqlalchemy as sa

revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s[:120] or "project"


def upgrade() -> None:
    op.add_column("projects", sa.Column("slug", sa.String(length=140), nullable=True))
    op.create_index("ix_projects_slug", "projects", ["slug"])

    # Backfill: slug per org, unique within org.
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, organization_id, name FROM projects ORDER BY created_at")).fetchall()
    used: dict[tuple, set] = {}
    for r in rows:
        org = r[1]
        base = _slugify(r[2])
        seen = used.setdefault(org, set())
        slug, n = base, 2
        while slug in seen:
            slug, n = f"{base}-{n}", n + 1
        seen.add(slug)
        conn.execute(sa.text("UPDATE projects SET slug = :s WHERE id = :i"), {"s": slug, "i": r[0]})


def downgrade() -> None:
    op.drop_index("ix_projects_slug", table_name="projects")
    op.drop_column("projects", "slug")
