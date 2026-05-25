#!/usr/bin/env python3
"""Seed example Sprint Management data for a Helix Migration project.

Usage:
    # From inside the backend container (DATABASE_URL is already set):
    python scripts/seed.py --org <ORG_UUID> --project <PROJECT_UUID>

    # From the host machine, pointing at the dev compose stack:
    DATABASE_URL=postgresql://helix:helix@localhost:5432/helix \\
        python scripts/seed.py --org <ORG_UUID> --project <PROJECT_UUID>

The seed is idempotent — running it twice produces the same DB state.
Wipes any pre-existing sprint rows for the target project before insert
so the demo dataset is deterministic.

For local dev with the dockerized stack, you can also POST to
    /api/v1/projects/{project_id}/sprints/seed
which calls the same function with auth + audit.

Equivalent to the seed.js convention in other stacks — Helix is Python.
"""

import argparse
import os
import sys
from pathlib import Path

# Allow running from repo root: scripts/seed.py
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Helix Migration sprint data")
    parser.add_argument("--org", required=True, help="Organization UUID")
    parser.add_argument("--project", required=True, help="Project UUID")
    parser.add_argument(
        "--db-url",
        default=os.environ.get("DATABASE_URL"),
        help="Postgres DSN (defaults to $DATABASE_URL)",
    )
    args = parser.parse_args()

    if not args.db_url:
        print("ERROR: DATABASE_URL not set and --db-url not provided", file=sys.stderr)
        return 2

    # Override env so the backend's settings module sees it.
    os.environ["DATABASE_URL"] = args.db_url

    # Import after PYTHONPATH + env are configured.
    from app.db.session import SessionLocal
    from app.services.sprint_seed import seed_sprints_for_project
    from app.models.project import Project  # ensures project FK is valid

    db = SessionLocal()
    try:
        project = db.query(Project).filter(
            Project.id == args.project,
            Project.organization_id == args.org,
        ).first()
        if not project:
            print(
                f"ERROR: project {args.project} not found for org {args.org}",
                file=sys.stderr,
            )
            return 3
        result = seed_sprints_for_project(db, args.org, args.project)
    finally:
        db.close()

    print("Seeded sprint dataset:")
    for k, v in result.items():
        print(f"  {k:<24} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
